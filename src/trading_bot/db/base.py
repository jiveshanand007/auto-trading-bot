"""SQLAlchemy engine, session factory, and declarative base.

Swapping SQLite (dev/tests) for Postgres (Docker) is a single config change in
``BOT_DATABASE_URL`` — the models stay portable by using generic column types.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from trading_bot.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def make_engine(url: str | None = None):
    url = url or get_settings().database_url
    return create_engine(url, future=True)


def make_session_factory(url: str | None = None):
    return sessionmaker(bind=make_engine(url), expire_on_commit=False, future=True)
