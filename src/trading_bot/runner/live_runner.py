from __future__ import annotations

import asyncio
import signal as _signal
from datetime import datetime, timezone

import uvloop
from binance import AsyncClient

from trading_bot.backtest.engine import signal_to_plan
from trading_bot.cli._broker_factory import make_futures_broker, make_spot_broker
from trading_bot.core.domain.portfolio import PortfolioState
from trading_bot.logging_config import configure_logging, get_logger
from trading_bot.market_data.binance_client import BinanceKlineClient
from trading_bot.market_data.downloader import raw_kline_to_bar
from trading_bot.market_data.types import Bar, Timeframe
from trading_bot.market_data.ws_feed import WsFeed
from trading_bot.risk.manager import RiskManager
from trading_bot.runner.config import RunnerConfig, StrategyConfig, load_config
from trading_bot.runner.config_selector import ConfigSelector

log = get_logger(__name__)

_WARMUP_BARS = 500


def _portfolio_state_from_broker(broker, symbol: str) -> PortfolioState:
    balance = broker.get_balance()
    equity = float(list(balance.values())[0].get("free", 0.0))
    positions = broker.get_positions(symbol)
    return PortfolioState(
        equity=equity,
        cash=equity,
        open_positions=positions,
        daily_start_equity=equity,
        is_halted=False,
    )


async def _warmup_bars(symbol: str, timeframe: Timeframe) -> list[Bar]:
    client = BinanceKlineClient()
    interval = timeframe.binance_interval
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    step_ms = int(timeframe.duration.total_seconds() * 1000)
    start_ms = end_ms - _WARMUP_BARS * step_ms
    raw = await asyncio.to_thread(
        client.fetch_klines, symbol, interval, start_ms, end_ms, _WARMUP_BARS
    )
    return [raw_kline_to_bar(r, symbol, timeframe) for r in raw]


async def _process_bar(
    bar: Bar, strategy, risk: RiskManager, broker, dry_run: bool
) -> None:
    portfolio = _portfolio_state_from_broker(broker, bar.symbol)
    signal = strategy.on_bar(bar, portfolio)
    if signal is None:
        return
    approved = risk.validate(signal, portfolio)
    if approved is None:
        log.info("signal_rejected", symbol=bar.symbol, reason="risk_check")
        return
    plan = signal_to_plan(approved)
    if dry_run:
        log.info(
            "dry_run_signal", symbol=bar.symbol, side=str(approved.side),
            entry=approved.entry_price, sl=approved.stop_loss, tp=approved.take_profit,
        )
        return
    result = await asyncio.to_thread(broker.place_trade, plan)
    log.info("trade_placed", symbol=bar.symbol, order_id=result.entry_order_id)


async def _run_symbol(
    strategy_cfg: StrategyConfig,
    runner_cfg: RunnerConfig,
    risk: RiskManager,
    ws_client: AsyncClient,
    dry_run: bool,
) -> None:
    symbol = strategy_cfg.symbol
    timeframe = Timeframe(strategy_cfg.timeframe)
    bound_log = log.bind(symbol=symbol, strategy=strategy_cfg.strategy)

    broker = make_spot_broker() if strategy_cfg.market == "spot" else make_futures_broker()
    selector = ConfigSelector(runner_cfg)
    strategy = selector.select(symbol, timeframe)

    bars = await _warmup_bars(symbol, timeframe)
    bound_log.info("warmup_complete", bars=len(bars))
    portfolio = _portfolio_state_from_broker(broker, symbol)
    for bar in bars:
        strategy.on_bar(bar, portfolio)

    queue: asyncio.Queue[Bar] = asyncio.Queue()
    feed = WsFeed(symbol, timeframe, queue)
    feed_task = asyncio.create_task(feed.run(ws_client))
    bound_log.info("live_runner_started", dry_run=dry_run)

    try:
        while True:
            bar = await queue.get()
            await _process_bar(bar, strategy, risk, broker, dry_run)
    except asyncio.CancelledError:
        feed_task.cancel()
        raise
    except Exception as exc:
        bound_log.error("symbol_error", error=str(exc))
        feed_task.cancel()
        raise


async def run(config_path: str, dry_run: bool = False) -> None:
    cfg = load_config(config_path)
    configure_logging()

    spot_risk = RiskManager()
    futures_risk = RiskManager()
    ws_client = await AsyncClient.create()

    tasks = [
        asyncio.create_task(
            _run_symbol(
                s, cfg,
                spot_risk if s.market == "spot" else futures_risk,
                ws_client, dry_run,
            ),
            name=f"{s.strategy}:{s.symbol}",
        )
        for s in cfg.strategies
    ]

    loop = asyncio.get_running_loop()

    def _shutdown():
        log.info("shutdown_initiated")
        for t in tasks:
            t.cancel()

    loop.add_signal_handler(_signal.SIGINT, _shutdown)
    loop.add_signal_handler(_signal.SIGTERM, _shutdown)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    await ws_client.close_connection()

    for task, result in zip(tasks, results, strict=True):
        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
            log.error("task_failed", task=task.get_name(), error=str(result))


def main(config_path: str = "runner.yaml", dry_run: bool = False) -> None:
    uvloop.install()
    asyncio.run(run(config_path, dry_run))
