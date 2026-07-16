"""Standalone PostgreSQL idempotency concurrency test.

The pytest suite runs on SQLite; true row-level concurrency (two sessions racing
the same INSERT under real MVCC + unique constraints) needs PostgreSQL. This
script drives two concurrent create_order() calls that share an Idempotency-Key
but carry DIFFERENT payloads, and asserts exactly one order is created while the
loser gets an idempotency conflict — never an order belonging to another payload.

Run directly (NOT under pytest, to avoid the SQLite conftest):

    DATABASE_URL=postgresql+asyncpg://user@host:5432/db python -m tests.postgres_concurrency

Exits non-zero on any failure. Mock/sandbox only — no real money.
"""

import asyncio
import os
import sys
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("PARTNER_WEBHOOK_SECRET", "pg-conc-webhook-secret-long-enough-00")
os.environ.setdefault("JWT_SECRET", "pg-conc-jwt-secret-long-enough-00000000")

from app.core.enums import OrderDirection  # noqa: E402
from app.core.errors import IdempotencyConflictError  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.models.order import Order  # noqa: E402
from app.partners.mock_fiat import MockFiatPartnerAdapter  # noqa: E402
from app.partners.registry import registry  # noqa: E402
from app.services.order_orchestrator import create_order  # noqa: E402
from app.services.quote_engine import create_quotes  # noqa: E402
from app.services.referral import generate_referral_code  # noqa: E402

# two distinct, individually-valid XMR addresses -> different fingerprints
WALLET_A = "4" + "AdUndXH2cfufTMvppY6JwXNouMBzSkbLYfpAV5Usx3skxNgYeYT".ljust(94, "z")
WALLET_B = "4" + "BdUndXH2cfufTMvppY6JwXNouMBzSkbLYfpAV5Usx3skxNgYeYT".ljust(94, "z")


def _require_postgres(url: str) -> None:
    if "postgresql" not in url:
        print(f"SKIP: DATABASE_URL is not PostgreSQL ({url!r})", file=sys.stderr)
        sys.exit(2)


async def _make_quote(factory, user_id: str):
    async with factory() as s:
        enriched = await create_quotes(
            s, user_id, OrderDirection.BUY, "RUB", None, "XMR", "XMR", Decimal("50000")
        )
        # pick the alpha partner quote deterministically
        return enriched[0]["quote"].id


async def _attempt(factory, user_id, quote_id, key, wallet, barrier):
    async with factory() as s:
        await barrier.wait()  # both requests hit create_order simultaneously
        try:
            order = await create_order(s, user_id, quote_id, key, wallet_address=wallet)
            return ("ok", order.id)
        except IdempotencyConflictError:
            return ("conflict", None)


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    _require_postgres(url)
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    db_session.set_session_factory(factory)

    registry._adapters.clear()
    registry.register_adapter(MockFiatPartnerAdapter())
    async with factory() as s:
        await registry.sync_partner_rows(s)
        from app.models.user import User

        user = User(
            telegram_id=888_001, username="conc", first_name="Conc",
            referral_code=generate_referral_code(),
        )
        s.add(user)
        await s.commit()
        user_id = user.id

    # --- scenario: same key, DIFFERENT payload, concurrent -> one order, one 409
    quote_id = await _make_quote(factory, user_id)
    key = uuid.uuid4().hex
    barrier = asyncio.Barrier(2)
    results = await asyncio.gather(
        _attempt(factory, user_id, quote_id, key, WALLET_A, barrier),
        _attempt(factory, user_id, quote_id, key, WALLET_B, barrier),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            raise AssertionError(f"unexpected exception from concurrent attempt: {r!r}")
    outcomes = sorted(r[0] for r in results)
    assert outcomes == ["conflict", "ok"], f"expected one ok + one conflict, got {outcomes}"

    async with factory() as s:
        n = (
            await s.execute(
                select(func.count()).select_from(Order).where(
                    Order.user_id == user_id, Order.idempotency_key == key
                )
            )
        ).scalar_one()
    assert n == 1, f"exactly one order must survive the race, found {n}"
    print(f"  concurrent same-key/different-payload: outcomes={outcomes}, orders={n}")

    # --- scenario: same key, SAME payload, sequential -> same order returned
    quote_id2 = await _make_quote(factory, user_id)
    key2 = uuid.uuid4().hex
    async with factory() as s:
        o1 = await create_order(s, user_id, quote_id2, key2, wallet_address=WALLET_A)
    async with factory() as s:
        o2 = await create_order(s, user_id, quote_id2, key2, wallet_address=WALLET_A)
    assert o1.id == o2.id, "same key + same payload must return the same order"
    print("  same-key/same-payload: returns same order")

    # --- scenario: same key, DIFFERENT quote -> conflict
    quote_id3 = await _make_quote(factory, user_id)
    conflicted = False
    async with factory() as s:
        try:
            await create_order(s, user_id, quote_id3, key2, wallet_address=WALLET_A)
        except IdempotencyConflictError:
            conflicted = True
    assert conflicted, "same key + different quote must raise idempotency conflict"
    print("  same-key/different-quote: conflict raised")

    # --- scenario: different users may share a key
    async with factory() as s:
        from app.models.user import User

        other = User(
            telegram_id=888_002, username="conc2", first_name="Conc2",
            referral_code=generate_referral_code(),
        )
        s.add(other)
        await s.commit()
        other_id = other.id
    quote_id4 = await _make_quote(factory, other_id)
    async with factory() as s:
        o = await create_order(s, other_id, quote_id4, key2, wallet_address=WALLET_A)
    assert o is not None, "different user may reuse the same idempotency key"
    print("  different-user/same-key: allowed")

    await engine.dispose()
    print("POSTGRES IDEMPOTENCY CONCURRENCY OK")


if __name__ == "__main__":
    asyncio.run(main())
