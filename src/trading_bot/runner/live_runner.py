from __future__ import annotations

import asyncio
import contextlib
import signal as _signal
from collections.abc import Callable
from datetime import date, datetime, timezone

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


def _spot_quote_asset(symbol: str) -> str:
    # Mirrors trading_bot.cli._display's quote-asset derivation.
    return "USDT" if "USDT" in symbol else "BUSD"


def _spot_equity_and_cash(balance: dict, symbol: str) -> tuple[float, float]:
    quote = balance.get(_spot_quote_asset(symbol), {})
    free = float(quote.get("free", 0.0))
    locked = float(quote.get("locked", 0.0))
    return free + locked, free


def _futures_equity_and_cash(balance: dict) -> tuple[float, float]:
    equity = float(balance.get("totalMarginBalance", 0.0))
    cash = float(balance.get("availableBalance", 0.0))
    return equity, cash


class _DailyEquityTracker:
    """Remembers a market's equity at the start of the current UTC day.

    `RiskManager`'s daily-drawdown circuit breaker needs a `daily_start_equity`
    that stays fixed for the whole UTC day, not the current equity recomputed on
    every call (which would make the drawdown check always read 0). Instantiate
    one tracker per market (spot/futures) — daily drawdown is account-level per
    market, not per-symbol.
    """

    def __init__(self, now_fn: Callable[[], datetime] | None = None) -> None:
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._date: date | None = None
        self._start_equity: float = 0.0

    def start_equity_for(self, current_equity: float) -> float:
        today = self._now_fn().date()
        if self._date != today:
            self._date = today
            self._start_equity = current_equity
        return self._start_equity


async def _portfolio_state_from_broker(
    broker, symbol: str, market: str, tracker: _DailyEquityTracker
) -> PortfolioState:
    balance = await asyncio.to_thread(broker.get_balance)
    positions = await asyncio.to_thread(broker.get_positions)

    if market == "futures":
        equity, cash = _futures_equity_and_cash(balance)
    else:
        equity, cash = _spot_equity_and_cash(balance, symbol)

    return PortfolioState(
        equity=equity,
        cash=cash,
        open_positions=positions,
        daily_start_equity=tracker.start_equity_for(equity),
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
    bar: Bar,
    strategy,
    risk: RiskManager,
    broker,
    dry_run: bool,
    market: str,
    daily_tracker: _DailyEquityTracker,
) -> None:
    portfolio = await _portfolio_state_from_broker(broker, bar.symbol, market, daily_tracker)
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


async def _next_bar(
    queue: asyncio.Queue[Bar], feed_task: asyncio.Task, symbol: str
) -> Bar:
    """Wait for the next bar, but race it against the feed task so a dead feed
    (ended cleanly or raised) surfaces immediately instead of hanging forever on
    `queue.get()`.
    """
    get_task = asyncio.ensure_future(queue.get())
    done, _pending = await asyncio.wait(
        {get_task, feed_task}, return_when=asyncio.FIRST_COMPLETED
    )
    if feed_task in done:
        get_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await get_task
        exc = feed_task.exception()
        if exc is not None:
            raise exc
        raise RuntimeError(f"WsFeed for {symbol} ended unexpectedly")
    return get_task.result()


async def _run_symbol(
    strategy_cfg: StrategyConfig,
    runner_cfg: RunnerConfig,
    risk: RiskManager,
    daily_tracker: _DailyEquityTracker,
    ws_client: AsyncClient,
    dry_run: bool,
) -> None:
    symbol = strategy_cfg.symbol
    market = strategy_cfg.market
    timeframe = Timeframe(strategy_cfg.timeframe)
    bound_log = log.bind(symbol=symbol, strategy=strategy_cfg.strategy)

    broker = make_spot_broker() if market == "spot" else make_futures_broker()
    selector = ConfigSelector(runner_cfg)
    strategy = selector.select(symbol, timeframe)

    bars = await _warmup_bars(symbol, timeframe)
    bound_log.info("warmup_complete", bars=len(bars))
    portfolio = await _portfolio_state_from_broker(broker, symbol, market, daily_tracker)
    for bar in bars:
        strategy.on_bar(bar, portfolio)

    queue: asyncio.Queue[Bar] = asyncio.Queue()
    feed = WsFeed(symbol, timeframe, queue)
    feed_task = asyncio.create_task(feed.run(ws_client))
    bound_log.info("live_runner_started", dry_run=dry_run)

    try:
        while True:
            bar = await _next_bar(queue, feed_task, symbol)
            await _process_bar(bar, strategy, risk, broker, dry_run, market, daily_tracker)
    except asyncio.CancelledError:
        feed_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await feed_task
        raise
    except Exception as exc:
        bound_log.error("symbol_error", error=str(exc))
        feed_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await feed_task
        raise


async def run(config_path: str, dry_run: bool = False) -> None:
    cfg = load_config(config_path)
    configure_logging()

    spot_risk = RiskManager()
    futures_risk = RiskManager()
    spot_daily = _DailyEquityTracker()
    futures_daily = _DailyEquityTracker()
    ws_client = await AsyncClient.create()

    tasks = [
        asyncio.create_task(
            _run_symbol(
                s, cfg,
                spot_risk if s.market == "spot" else futures_risk,
                spot_daily if s.market == "spot" else futures_daily,
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
