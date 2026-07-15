"""Full PostgreSQL MVP money-flow integration test.

Requires POSTGRES_TEST_DATABASE_URL. Isolated with NullPool + function loop
to avoid asyncpg/event-loop clashes with the SQLite session suite.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.enums import CircuitBreakerState, QuoteSourceType
from app.main import app, polling_worker
from app.models import Base, Order, Partner, PaymentInstructions, Quote
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
async def test_postgres_full_mvp_money_flow(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("ENABLE_DEV_ENDPOINTS", "true")
    get_settings.cache_clear()
    settings = get_settings()
    settings.enable_dev_endpoints = True
    settings.emergency_stop = False
    settings.rate_limit_per_minute = 100_000
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
                json={"init_data": make_init_data(telegram_id=700001, username="pg_mvp")},
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
                    "amount_in": 15000,
                    "payment_method": "SBP",
                    "bank_name": "Sber",
                },
            )
            assert quote_resp.status_code == 200, quote_resp.text
            body = quote_resp.json()
            assert body["best"] is not None
            assert body["best"]["root_score"] == max(q["root_score"] for q in body["all"])
            quote_id = body["best"]["id"]

            key = str(uuid.uuid4())
            order_resp = await client.post(
                "/api/v1/orders",
                headers=headers,
                json={
                    "quote_id": quote_id,
                    "idempotency_key": key,
                    "wallet_address": XMR_TEST_ADDRESS,
                    "payment_method": "SBP",
                    "bank_name": "Sber",
                },
            )
            assert order_resp.status_code == 200, order_resp.text
            order = order_resp.json()
            assert order["status"] == "AWAITING_PAYMENT"
            assert order["payment_instructions"]["amount"] == 15000.0
            assert order["payment_instructions"]["sbp_phone"]
            order_id = order["id"]

            async with factory() as sess:
                db_order = (
                    await sess.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
                ).scalar_one()
                db_pi = (
                    await sess.execute(
                        select(PaymentInstructions).where(
                            PaymentInstructions.order_id == db_order.id
                        )
                    )
                ).scalar_one()
                assert db_order.payment_instructions_id == db_pi.id
                assert db_pi.order_id == db_order.id
                n = await sess.execute(
                    text("SELECT COUNT(*) FROM payment_instructions WHERE order_id = :oid"),
                    {"oid": db_order.id},
                )
                assert n.scalar_one() == 1
                fk = await sess.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM pg_constraint con
                        JOIN pg_class rel ON rel.oid = con.conrelid
                        WHERE rel.relname = 'orders'
                          AND con.contype = 'f'
                          AND pg_get_constraintdef(con.oid) LIKE '%payment_instructions%'
                        """
                    )
                )
                assert fk.scalar_one() == 0
                q = (
                    await sess.execute(select(Quote).where(Quote.id == uuid.UUID(quote_id)))
                ).scalar_one()
                assert q.consumed_at is not None

            sim = await client.post(
                f"/api/v1/orders/{order_id}/simulate-payment", headers=headers
            )
            assert sim.status_code == 200, sim.text
            assert sim.json()["status"] == "COMPLETED"

            async with factory() as sess:
                db_order = (
                    await sess.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
                ).scalar_one()
                assert db_order.status.value == "COMPLETED"
                pi_count = await sess.execute(text("SELECT COUNT(*) FROM payment_instructions"))
                order_count = await sess.execute(text("SELECT COUNT(*) FROM orders"))
                assert pi_count.scalar_one() == order_count.scalar_one()

            again = await client.post(
                "/api/v1/orders",
                headers=headers,
                json={
                    "quote_id": quote_id,
                    "idempotency_key": key,
                    "wallet_address": XMR_TEST_ADDRESS,
                    "payment_method": "SBP",
                    "bank_name": "Sber",
                },
            )
            assert again.status_code == 200
            assert again.json()["id"] == order_id
            async with factory() as sess:
                n = await sess.execute(text("SELECT COUNT(*) FROM orders"))
                assert n.scalar_one() == 1
    finally:
        app.dependency_overrides.clear()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        get_settings.cache_clear()


@requires_postgres
@pytest.mark.asyncio(loop_scope="function")
async def test_postgres_unique_pi_constraint(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("ENABLE_DEV_ENDPOINTS", "true")
    get_settings.cache_clear()
    settings = get_settings()
    settings.enable_dev_endpoints = True

    engine = create_async_engine(PG_URL, poolclass=NullPool, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        sess.add(
            Partner(
                code="mock_fiat",
                name="Mock Fiat",
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

    db_session.async_session_factory = factory
    polling_worker.stop()

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
                json={"init_data": make_init_data(telegram_id=700002)},
            )
            headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}
            quote = await client.post(
                "/api/v1/quotes",
                headers=headers,
                json={
                    "direction": "BUY",
                    "from_asset": "RUB",
                    "to_asset": "BTC",
                    "to_network": "BTC",
                    "amount_in": 20000,
                },
            )
            order = await client.post(
                "/api/v1/orders",
                headers=headers,
                json={
                    "quote_id": quote.json()["best"]["id"],
                    "idempotency_key": str(uuid.uuid4()),
                    "wallet_address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                },
            )
            assert order.status_code == 200
            oid = uuid.UUID(order.json()["id"])

        async with factory() as sess:
            sess.add(
                PaymentInstructions(
                    id=uuid.uuid4(),
                    order_id=oid,
                    payment_method="SBP",
                    amount=1,
                    currency="RUB",
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                )
            )
            with pytest.raises(Exception):
                await sess.flush()
            await sess.rollback()
    finally:
        app.dependency_overrides.clear()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        get_settings.cache_clear()
