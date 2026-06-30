"""Binance-specific error handling and mapping."""

from __future__ import annotations

from binance.exceptions import BinanceAPIException, BinanceOrderException


class BrokerError(Exception):
    """Unified broker error wrapper for Binance exceptions."""

    def __init__(
        self,
        message: str,
        code: int | None = None,
        original: Exception | None = None,
    ) -> None:
        """Initialize BrokerError.

        Args:
            message: Human-readable error message.
            code: Numeric error code from the broker.
            original: Original exception from the broker library.
        """
        super().__init__(message)
        self.code = code
        self.original = original


def map_binance_error(exc: BinanceAPIException | BinanceOrderException) -> BrokerError:
    """Map a Binance exception to a BrokerError.

    Args:
        exc: Binance exception from python-binance.

    Returns:
        BrokerError wrapping the original exception.
    """
    code = getattr(exc, "code", None)
    return BrokerError(str(exc), code=code, original=exc)
