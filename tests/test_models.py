"""Schema tests: all tables create, and every table carries the account_id seam."""

from sqlalchemy import create_engine, inspect

from trading_bot.db import models  # noqa: F401  (registers models on Base.metadata)
from trading_bot.db.base import Base

EXPECTED_TABLES = {
    "accounts",
    "strategies",
    "runs",
    "orders",
    "fills",
    "positions",
    "equity_snapshots",
}

# accounts is the seam's root, so it owns the id rather than an account_id column.
TABLES_WITH_ACCOUNT_ID = EXPECTED_TABLES - {"accounts"}


def _created_inspector():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return inspect(engine)


def test_all_expected_tables_created():
    insp = _created_inspector()
    assert EXPECTED_TABLES.issubset(set(insp.get_table_names()))


def test_every_table_has_account_id_seam():
    insp = _created_inspector()
    for table in TABLES_WITH_ACCOUNT_ID:
        cols = {c["name"] for c in insp.get_columns(table)}
        assert "account_id" in cols, f"{table} missing account_id seam"


def test_order_client_order_id_is_unique():
    insp = _created_inspector()
    uniques = insp.get_unique_constraints("orders")
    unique_cols = {tuple(u["column_names"]) for u in uniques}
    # Either a named unique constraint or a unique index on client_order_id.
    indexes = {tuple(i["column_names"]) for i in insp.get_indexes("orders") if i["unique"]}
    assert ("client_order_id",) in unique_cols | indexes


def test_position_uniqueness_per_run_symbol():
    insp = _created_inspector()
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("positions")}
    assert ("account_id", "run_id", "symbol") in uniques
