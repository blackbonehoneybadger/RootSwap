"""Standalone Alembic migration scenarios against a real PostgreSQL server.

The pytest suite runs on SQLite; the migration guards in 0002 (duplicate /
NULL ``payment_instructions.order_id`` detection, dialect-specific aggregate
SQL) and the 0003 auth_sessions idempotency are only meaningful on PostgreSQL.
This script drives Alembic programmatically through five scenarios and asserts
both success paths and the deliberate fail-closed guards, proving no migration
silently deletes data.

Run directly (NOT under pytest):

    DATABASE_URL=postgresql+asyncpg://user:pw@host:5432/db \
    PG_ADMIN_DSN=postgresql://user:pw@host:5432/postgres \
    python -m tests.postgres_migrations

Exits non-zero on any failure. Mock/sandbox only — no real money.
"""

import asyncio
import os
import sys

import asyncpg

from alembic import command
from alembic.config import Config

# asyncpg DSN (NOT the SQLAlchemy +asyncpg form) for admin + data operations.
_ADMIN = os.environ.get(
    "PG_ADMIN_DSN", "postgresql://rootswap:rootswap@localhost:5432/postgres"
)
# host:port/credentials base, database name appended per scenario.
_BASE = _ADMIN.rsplit("/", 1)[0]
_DB = "rs_migscratch"


def _sqla_url(db: str) -> str:
    # translate the libpq DSN base into a SQLAlchemy asyncpg URL
    tail = _BASE.split("://", 1)[1]
    return f"postgresql+asyncpg://{tail}/{db}"


def _run(coro):
    return asyncio.run(coro)


async def _admin_exec(sql: str) -> None:
    conn = await asyncpg.connect(_ADMIN)
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


async def _exec(db: str, statements: list[str]) -> None:
    conn = await asyncpg.connect(f"{_BASE}/{db}")
    try:
        for s in statements:
            await conn.execute(s)
    finally:
        await conn.close()


async def _fetchval(db: str, sql: str):
    conn = await asyncpg.connect(f"{_BASE}/{db}")
    try:
        return await conn.fetchval(sql)
    finally:
        await conn.close()


async def _table_names(db: str) -> set[str]:
    conn = await asyncpg.connect(f"{_BASE}/{db}")
    try:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )
        return {r["tablename"] for r in rows}
    finally:
        await conn.close()


def _fresh_db() -> None:
    _run(_admin_exec(f"DROP DATABASE IF EXISTS {_DB}"))
    _run(_admin_exec(f"CREATE DATABASE {_DB}"))


def _cfg() -> Config:
    os.environ["DATABASE_URL"] = _sqla_url(_DB)
    return Config("alembic.ini")


async def _drop_fks(db: str, table: str) -> None:
    conn = await asyncpg.connect(f"{_BASE}/{db}")
    try:
        rows = await conn.fetch(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = $1::regclass AND contype = 'f'",
            table,
        )
        for r in rows:
            await conn.execute(f'ALTER TABLE {table} DROP CONSTRAINT "{r["conname"]}"')
    finally:
        await conn.close()


def _to_legacy_pi_shape() -> None:
    """Revert payment_instructions/orders to the genuine pre-0002 shape so the
    0002 guards can be exercised: no unique(order_id), no fingerprint column,
    and a nullable order_id (an older schema variant)."""
    _run(_drop_fks(_DB, "payment_instructions"))
    _run(
        _exec(
            _DB,
            [
                "ALTER TABLE payment_instructions "
                "DROP CONSTRAINT IF EXISTS uq_payment_instructions_order_id",
                "ALTER TABLE payment_instructions ALTER COLUMN order_id DROP NOT NULL",
                "ALTER TABLE orders DROP COLUMN IF EXISTS idempotency_fingerprint",
            ],
        )
    )


def _insert_pi(order_id_sql: str, pk: str) -> str:
    return (
        "INSERT INTO payment_instructions "
        "(id, order_id, payment_method, amount, currency, expires_at, created_at) "
        f"VALUES ('{pk}', {order_id_sql}, 'SBP', 1000, 'RUB', now(), now())"
    )


def scenario_clean_upgrade() -> None:
    _fresh_db()
    command.upgrade(_cfg(), "head")
    tables = _run(_table_names(_DB))
    for expected in ("users", "orders", "payment_instructions", "auth_sessions"):
        assert expected in tables, f"missing table {expected} after clean upgrade"
    rev = _run(_fetchval(_DB, "SELECT version_num FROM alembic_version"))
    assert rev == "0003_auth_sessions", f"unexpected head revision {rev}"
    print("  1. clean upgrade from empty -> head OK")


def scenario_downgrade_upgrade_roundtrip() -> None:
    _fresh_db()
    cfg = _cfg()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    tables = _run(_table_names(_DB))
    assert "orders" not in tables, "downgrade base must drop schema"
    command.upgrade(cfg, "head")
    tables = _run(_table_names(_DB))
    assert "auth_sessions" in tables, "re-upgrade must rebuild schema"
    print("  2. downgrade base -> upgrade head round-trip OK")


def scenario_legacy_duplicate_order_id() -> None:
    _fresh_db()
    cfg = _cfg()
    command.upgrade(cfg, "0001_initial")
    _to_legacy_pi_shape()
    _run(
        _exec(
            _DB,
            [
                _insert_pi("'dup-order-1'", "pi-a"),
                _insert_pi("'dup-order-1'", "pi-b"),
            ],
        )
    )
    raised = False
    try:
        command.upgrade(cfg, "0002_pi_unique")
    except Exception as exc:  # noqa: BLE001 - migration guard is a RuntimeError
        raised = True
        assert "duplicate" in str(exc).lower(), f"unexpected error: {exc}"
    assert raised, "0002 must refuse to add UNIQUE when duplicates exist"
    # fail-closed: the duplicate rows must still be present (no silent delete)
    n = _run(_fetchval(_DB, "SELECT count(*) FROM payment_instructions"))
    assert n == 2, f"guard must not delete data, found {n} rows"
    print("  3. legacy duplicate order_id -> 0002 fails closed, no delete OK")


def scenario_legacy_null_order_id() -> None:
    _fresh_db()
    cfg = _cfg()
    command.upgrade(cfg, "0001_initial")
    _to_legacy_pi_shape()
    _run(_exec(_DB, [_insert_pi("NULL", "pi-null")]))
    raised = False
    try:
        command.upgrade(cfg, "0002_pi_unique")
    except Exception as exc:  # noqa: BLE001
        raised = True
        assert "null" in str(exc).lower(), f"unexpected error: {exc}"
    assert raised, "0002 must refuse to add UNIQUE when NULL order_id exists"
    n = _run(_fetchval(_DB, "SELECT count(*) FROM payment_instructions"))
    assert n == 1, f"guard must not delete data, found {n} rows"
    print("  4. legacy NULL order_id -> 0002 fails closed, no delete OK")


def scenario_production_like_preserves_data() -> None:
    """A populated database must survive the newest migration boundary: unrelated
    rows are preserved across a 0003<->0002 downgrade/upgrade cycle."""
    _fresh_db()
    cfg = _cfg()
    command.upgrade(cfg, "head")
    _run(
        _exec(
            _DB,
            [
                "INSERT INTO users (id, telegram_id, referral_code, referral_tier, "
                "is_blocked, created_at, updated_at) "
                "VALUES ('u-prod-1', 424242, 'prodref01', 1, false, now(), now())",
            ],
        )
    )
    command.downgrade(cfg, "0002_pi_unique")  # drops auth_sessions only
    assert "auth_sessions" not in _run(_table_names(_DB))
    command.upgrade(cfg, "head")  # rebuilds auth_sessions
    assert "auth_sessions" in _run(_table_names(_DB))
    survived = _run(
        _fetchval(_DB, "SELECT count(*) FROM users WHERE id = 'u-prod-1'")
    )
    assert survived == 1, "unrelated user data must survive the migration cycle"
    print("  5. production-like data preserved across migration cycle OK")


def main() -> None:
    if "postgresql" not in _ADMIN:
        print(f"SKIP: PG_ADMIN_DSN is not PostgreSQL ({_ADMIN!r})", file=sys.stderr)
        sys.exit(2)
    scenario_clean_upgrade()
    scenario_downgrade_upgrade_roundtrip()
    scenario_legacy_duplicate_order_id()
    scenario_legacy_null_order_id()
    scenario_production_like_preserves_data()
    _run(_admin_exec(f"DROP DATABASE IF EXISTS {_DB}"))
    print("POSTGRES MIGRATION SCENARIOS OK")


if __name__ == "__main__":
    main()
