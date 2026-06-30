from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, field_validator


class StrategyConfig(BaseModel):
    strategy: Literal["ma-crossover", "rsi"]
    symbol: str
    timeframe: str
    market: Literal["spot", "futures"]
    params: dict[str, Any] = {}

    @field_validator("timeframe")
    @classmethod
    def _validate_timeframe(cls, v: str) -> str:
        from trading_bot.market_data.types import Timeframe

        Timeframe(v)
        return v


class RunnerConfig(BaseModel):
    capital: float = 10_000.0
    fee_rate: float = 0.001
    strategies: list[StrategyConfig]


def load_config(path: str | Path) -> RunnerConfig:
    raw = yaml.safe_load(Path(path).read_text())
    return RunnerConfig.model_validate(raw)
