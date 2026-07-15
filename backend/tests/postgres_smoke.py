"""Standalone PostgreSQL write-path smoke test.

The pytest suite runs on SQLite (see tests/conftest.py), so a bug that only
manifests on PostgreSQL — a circular foreign key, a flush ordering problem, a
dialect-specific type mismatch — would pass the SQLite suite unnoticed. This
script exercises the real money path against the actual production database
engine and is wired into CI (.github/workflows/backend.yml) after migrations.

Run it directly (NOT under pytest, to avoid the SQLite conftest):

    DATABASE_URL=postgresql+asyncpg://user@host:5432/db python -m tests.postgres_smoke

Exits non-zero on any failure. Mock/sandbox only — no real money.
"""

import asyncio
import json
import os
import sys
import time
import uuid
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Test env must be set before app modules import settings.
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("PARTNER_WEBHOOK_SECRET", "pg-smoke-webhook-secret-long-enough-0")
os.environ.setdefault("JWT_SECRET", "pg-smoke-jwt-secret-long-enough-000000")

from app.core.enums import OrderDirection, OrderStatus  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.models.ledger import LedgerEntry  # noqa: E402
from app.models.payment_instructions import PaymentInstructions  # noqa: E402
from app.models.referral import ReferralReward  # noqa: E402
from app.models.user import User  # noqa: E402
from app.partners.mock_fiat import MockFiatPartnerAdapter, sign_mock_webhook  # noqa: E402
from app.partners.registry import registry  # noqa: E402
from app.services.ledger import reconcile  # noqa: E402
from app.services.order_orchestrator import create_order  # noqa: E402
from app.services.quote_engine import create_quotes  # noqa: E402
from app.services.referral import attach_referrer, generate_referral_code  # noqa: E402
from app.services.webhook_processor import ingest_webhook  # noqa: E402


def _require_postgres(url: str) -> None:
    if "postgresql" not in url:
        print(f"SKIP: DATABASE_URL is not PostgreSQL ({url!r})", file=sys.stderr)
        sys.exit(2)


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

        # referrer + referred user (referral must accrue on Postgres too)
        referrer = User(
            telegram_id=777_100, username="ref", first_name="Ref",
            referral_code=generate_referral_code(),
        )
        s.add(referrer)
        await s.flush()
        user = User(
            telegram_id=777_101, username="pg", first_name="PG",
            referral_code=generate_referral_code(),
        )
        s.add(user)
        await s.flush()
        await attach_referrer(s, user, referrer.referral_code)
        await s.commit()

        # quote -> order (this is the flush path that fails on a circular FK)
        enriched = await create_quotes(
            s, user.id, OrderDirection.BUY, "RUB", None, "XMR", "XMR", Decimal("50000")
        )
        quote = enriched[0]["quote"]
        order = await create_order(
            s, user.id, quote.id, uuid.uuid4().hex, wallet_address="4" + "A" * 94
        )
        assert order.status == OrderStatus.AWAITING_PAYMENT, order.status
        assert order.payment_instructions_id is not None
        pi = (
            await s.execute(
                select(PaymentInstructions).where(PaymentInstructions.order_id == order.id)
            )
        ).scalar_one()
        assert pi.id == order.payment_instructions_id, "order <-> PI link mismatch"
        partner_order_id = order.partner_order_id
        order_id = order.id
        print(f"  order created: {order.status.value}, PI bank={pi.bank_name}")

    # webhook -> COMPLETED drives ledger + referral on Postgres
    payload = json.dumps(
        {
            "event_id": uuid.uuid4().hex,
            "event_type": "completed",
            "partner_order_id": partner_order_id,
        }
    ).encode()
    ts = str(int(time.time()))
    sig = sign_mock_webhook(payload, ts)
    async with factory() as s:
        await registry.sync_partner_rows(s)
        event = await ingest_webhook(s, "mock_fiat_alpha", payload, sig, ts)
        assert event.processing_status.value == "PROCESSED", event.processing_error

    async with factory() as s:
        from app.models.order import Order

        order = (await s.execute(select(Order).where(Order.id == order_id))).scalar_one()
        assert order.status == OrderStatus.COMPLETED, order.status
        gross = (
            await s.execute(
                select(LedgerEntry).where(
                    LedgerEntry.posting_key == f"order:{order_id}:gross_service_fee"
                )
            )
        ).scalars().all()
        assert len(gross) == 1, f"expected 1 gross posting, got {len(gross)}"
        rewards = (
            await s.execute(
                select(ReferralReward).where(ReferralReward.order_id == order_id)
            )
        ).scalars().all()
        assert len(rewards) == 1, f"expected 1 referral reward, got {len(rewards)}"
        recon = await reconcile(s)
        assert recon["balanced"], recon
        print(f"  completed: ledger balanced={recon['balanced']}, reward accrued=1")

    # no circular FK: orders must not reference payment_instructions
    async with engine.connect() as c:
        rows = (
            await c.execute(
                text(
                    "select conname from pg_constraint "
                    "where contype='f' and conrelid='orders'::regclass"
                )
            )
        ).fetchall()
        fks = [r[0] for r in rows]
        assert not any("payment" in f.lower() for f in fks), f"circular FK present: {fks}"
        print(f"  orders FKs: {fks} (no circular FK)")

    await engine.dispose()
    print("POSTGRES SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
