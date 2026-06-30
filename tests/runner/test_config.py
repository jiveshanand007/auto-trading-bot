from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from trading_bot.runner.config import RunnerConfig, load_config

_VALID_YAML = textwrap.dedent("""
    capital: 10000.0
    fee_rate: 0.001
    strategies:
      - strategy: ma-crossover
        symbol: BTCUSDT
        timeframe: H1
        market: spot
        params:
          fast: 9
          slow: 21
      - strategy: rsi
        symbol: ETHUSDT
        timeframe: H1
        market: futures
        params:
          period: 14
""")


def test_load_config_valid(tmp_path: Path):
    cfg_file = tmp_path / "runner.yaml"
    cfg_file.write_text(_VALID_YAML)
    cfg = load_config(cfg_file)
    assert isinstance(cfg, RunnerConfig)
    assert cfg.capital == 10_000.0
    assert len(cfg.strategies) == 2


def test_strategy_config_fields(tmp_path: Path):
    cfg_file = tmp_path / "runner.yaml"
    cfg_file.write_text(_VALID_YAML)
    cfg = load_config(cfg_file)
    s = cfg.strategies[0]
    assert s.strategy == "ma-crossover"
    assert s.symbol == "BTCUSDT"
    assert s.timeframe == "H1"
    assert s.market == "spot"
    assert s.params == {"fast": 9, "slow": 21}


def test_invalid_strategy_name_rejected(tmp_path: Path):
    bad = _VALID_YAML.replace("ma-crossover", "unknown-strategy")
    cfg_file = tmp_path / "runner.yaml"
    cfg_file.write_text(bad)
    with pytest.raises(ValidationError):
        load_config(cfg_file)


def test_invalid_market_rejected(tmp_path: Path):
    bad = _VALID_YAML.replace("market: spot", "market: crypto")
    cfg_file = tmp_path / "runner.yaml"
    cfg_file.write_text(bad)
    with pytest.raises(ValidationError):
        load_config(cfg_file)


def test_invalid_timeframe_rejected(tmp_path: Path):
    bad = _VALID_YAML.replace("timeframe: H1", "timeframe: X9")
    cfg_file = tmp_path / "runner.yaml"
    cfg_file.write_text(bad)
    with pytest.raises(ValidationError):
        load_config(cfg_file)


def test_defaults_applied(tmp_path: Path):
    minimal = textwrap.dedent("""
        strategies:
          - strategy: ma-crossover
            symbol: BTCUSDT
            timeframe: H1
            market: spot
    """)
    cfg_file = tmp_path / "runner.yaml"
    cfg_file.write_text(minimal)
    cfg = load_config(cfg_file)
    assert cfg.capital == 10_000.0
    assert cfg.fee_rate == 0.001
    assert cfg.strategies[0].params == {}
