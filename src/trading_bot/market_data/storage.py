"""Parquet-backed OHLCV storage, partitioned by symbol and timeframe.

Layout::

    <root>/symbol=BTCUSDT/timeframe=H1/data.parquet

Parquet (via pyarrow) is columnar and fast for the backtest replay loop, and
needs no running service. Prices are stored as strings to preserve Decimal
exactness on the round-trip.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd

from trading_bot.market_data.types import Bar, Timeframe

_PRICE_COLS = ("open", "high", "low", "close", "volume")
_FILENAME = "data.parquet"


class ParquetBarStore:
    """Read/write :class:`Bar` collections as partitioned parquet files."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    # --- paths -------------------------------------------------------------
    def _partition_dir(self, symbol: str, timeframe: Timeframe) -> Path:
        return self.root / f"symbol={symbol}" / f"timeframe={timeframe.value}"

    def _path(self, symbol: str, timeframe: Timeframe) -> Path:
        return self._partition_dir(symbol, timeframe) / _FILENAME

    # --- write -------------------------------------------------------------
    def write(self, bars: list[Bar]) -> None:
        """Append bars, de-duplicating on open_time and keeping sorted order.

        All bars must share the same symbol and timeframe.
        """
        if not bars:
            return
        symbol = bars[0].symbol
        timeframe = bars[0].timeframe
        if any(b.symbol != symbol or b.timeframe != timeframe for b in bars):
            raise ValueError("write() requires a single symbol/timeframe per call")

        existing = self.read(symbol, timeframe)
        merged: dict[datetime, Bar] = {b.open_time: b for b in existing}
        for b in bars:  # new bars win on conflict
            merged[b.open_time] = b
        ordered = [merged[t] for t in sorted(merged)]

        path = self._path(symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._to_frame(ordered).to_parquet(path, index=False)

    # --- read --------------------------------------------------------------
    def read(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Bar]:
        """Return bars sorted by open_time, optionally filtered to [start, end]."""
        path = self._path(symbol, timeframe)
        if not path.exists():
            return []
        df = pd.read_parquet(path)
        bars = [self._row_to_bar(row, symbol, timeframe) for row in df.to_dict("records")]
        if start is not None:
            bars = [b for b in bars if b.open_time >= start]
        if end is not None:
            bars = [b for b in bars if b.open_time <= end]
        return bars

    # --- (de)serialization -------------------------------------------------
    @staticmethod
    def _to_frame(bars: list[Bar]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open_time": [b.open_time for b in bars],
                "close_time": [b.close_time for b in bars],
                "open": [str(b.open) for b in bars],
                "high": [str(b.high) for b in bars],
                "low": [str(b.low) for b in bars],
                "close": [str(b.close) for b in bars],
                "volume": [str(b.volume) for b in bars],
            }
        )

    @staticmethod
    def _row_to_bar(row: dict, symbol: str, timeframe: Timeframe) -> Bar:
        return Bar(
            symbol=symbol,
            timeframe=timeframe,
            open_time=_as_utc(row["open_time"]),
            close_time=_as_utc(row["close_time"]),
            **{c: Decimal(str(row[c])) for c in _PRICE_COLS},
        )


def _as_utc(value) -> datetime:
    """Normalize a pandas/py datetime to a tz-aware UTC datetime."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(timezone.utc)
    return ts.to_pydatetime()
