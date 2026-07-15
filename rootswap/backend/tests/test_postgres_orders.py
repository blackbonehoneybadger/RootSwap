"""PostgreSQL-only integration: order create must not hit circular FK errors.

Skipped unless POSTGRES_TEST_DATABASE_URL points at PostgreSQL.
Isolated from the session-scoped SQLite fixtures (asyncpg + session loop clashes).
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.enums import CircuitBreakerState, QuoteSourceType
from app.main import app, polling_worker
from app.models import Base, Order, Partner, PaymentInstructions
from tests.conftest import XMR_TEST_ADDRESS, make_init_data

PG_URL = os.getenv(
    "POSTGRES_TEST_DATABASE_URL",
    "postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap_test",
)

BOT_TOKEN = "0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER"

requires_postgres = pytest.mark.skipif(
    not PG_URL.startswith("postgresql"),
    reason="Set POSTGRES_TEST_DATABASE_URL to a PostgreSQL DSN",
)


@requires_postgres
@pytest.mark.asyncio(loop_scope="function")
async def test_postgres_create_order_with_payment_instructions(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    get_settings.cache_clear()
    # RateLimitMiddleware caches settings at import — clear Redis counters.
    try:
        import redis as sync_redis

        sync_redis.from_url(get_settings().redis_url, decode_responses=True).flushdb()
    except Exception:
        pass

    engine = create_async_engine(PG_URL, poolclass=NullPool, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as sess:
        for code, name in (("mock_fiat", "Mock Fiat"), ("mock_fiat_backup", "Mock Backup")):
            sess.add(
                Partner(
                    code=code,
                    name=name,
                    adapter_type="mock_fiat",
                    enabled=True,
                    quote_source_type=QuoteSourceType.MOCK,
                    environment="sandbox",
                    circuit_breaker_state=CircuitBreakerState.CLOSED,
                )
            )
        await sess.commit()

    from app.db import session as db_session
    from app.db.session import get_db
    from app.partners.registry import partner_registry

    db_session.async_session_factory = factory
    polling_worker.stop()
    for adapter in partner_registry._adapters.values():
        if hasattr(adapter, "set_scenario"):
            adapter.set_scenario(None)

    async def override_get_db():
        async with factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            auth = await client.post(
                "/api/v1/auth/telegram",
                json={"init_data": make_init_data(telegram_id=555001)},
            )
            assert auth.status_code == 200, auth.text
            headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}

            quote_resp = await client.post(
                "/api/v1/quotes",
                headers=headers,
                json={
                    "direction": "BUY",
                    "from_asset": "RUB",
                    "to_asset": "XMR",
                    "to_network": "XMR",
                    "amount_in": 10000,
                    "payment_method": "SBP",
                    "bank_name": "Sber",
                },
            )
            assert quote_resp.status_code == 200, quote_resp.text
            quote_id = quote_resp.json()["best"]["id"]

            order_resp = await client.post(
                "/api/v1/orders",
                headers=headers,
                json={
                    "quote_id": quote_id,
                    "idempotency_key": str(uuid.uuid4()),
                    "wallet_address": XMR_TEST_ADDRESS,
                    "payment_method": "SBP",
                    "bank_name": "Sber",
                },
            )
            assert order_resp.status_code == 200, order_resp.text
            body = order_resp.json()
            assert body["status"] == "AWAITING_PAYMENT"
            assert body["payment_instructions"] is not None
            order_id = body["id"]

        async with factory() as sess:
            order = (
                await sess.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
            ).scalar_one()
            assert order.payment_instructions_id is not None

            pi = (
                await sess.execute(
                    select(PaymentInstructions).where(
                        PaymentInstructions.id == order.payment_instructions_id
                    )
                )
            ).scalar_one()
            assert pi.order_id == order.id
            assert pi.deleted_at is None
            assert order.payment_instructions_id == pi.id

            orphan_pi = (
                await sess.execute(
                    select(PaymentInstructions).where(PaymentInstructions.order_id.is_(None))
                )
            ).scalars().all()
            assert orphan_pi == []

            fks = (
                await sess.execute(
                    text(
                        """
                        SELECT con.conname
                        FROM pg_constraint con
                        JOIN pg_class rel ON rel.oid = con.conrelid
                        WHERE rel.relname = 'orders'
                          AND con.contype = 'f'
                          AND pg_get_constraintdef(con.oid) LIKE '%payment_instructions%'
                        """
                    )
                )
            ).fetchall()
            assert fks == [], f"unexpected circular FKs still present: {fks}"
    finally:
        app.dependency_overrides.clear()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        get_settings.cache_clear()
