"""Application configuration loaded from environment / .env.

Single source of truth for settings. SaaS-later note: per-account broker
credentials are NOT modeled here yet — these are the single-operator defaults.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BOT_",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = Field(
        default="postgresql+psycopg2://bot:bot@localhost:5432/trading_bot",
        description="SQLAlchemy URL for the Postgres database.",
    )

    # --- Market data storage ---
    data_dir: Path = Field(
        default=PROJECT_ROOT / "data",
        description="Root directory for parquet OHLCV storage.",
    )

    # --- Binance ---
    binance_api_key: str = Field(default="", description="Binance API key (live/testnet).")
    binance_api_secret: str = Field(default="", description="Binance API secret.")
    binance_testnet: bool = Field(default=True, description="Use Binance testnet endpoints.")
    binance_testnet_url: str = Field(
        default="https://testnet.binance.vision/api",
        description="Spot testnet REST base URL (only used when binance_testnet=True).",
    )
    binance_live_url: str = Field(
        default="https://api.binance.com/api",
        description="Live REST base URL (only used when binance_testnet=False).",
    )

    # --- Binance Futures (USDM) ---
    futures_leverage: int = Field(
        default=5, description="Default leverage for futures trades (1–125)."
    )
    futures_margin_type: str = Field(
        default="ISOLATED", description="Default margin type: ISOLATED or CROSS."
    )
    binance_futures_testnet: bool = Field(
        default=True, description="Use futures testnet endpoint."
    )
    binance_futures_testnet_url: str = Field(
        default="https://testnet.binancefuture.com/fapi",
        description="USDM futures testnet REST base URL.",
    )
    binance_futures_live_url: str = Field(
        default="https://fapi.binance.com/fapi",
        description="USDM futures live REST base URL.",
    )

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False, description="Emit JSON logs (True in prod).")


def get_settings() -> Settings:
    """Return a fresh Settings instance (reads env each call)."""
    return Settings()
