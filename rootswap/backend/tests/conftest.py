import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.enums import CircuitBreakerState, QuoteSourceType
from app.main import app
from app.models import Base, Partner

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_rootswap.db",
)
BOT_TOKEN = "0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER"
XMR_TEST_ADDRESS = "49" + "A" * 93
TRON_TEST_ADDRESS = "T" + "A" * 33

def make_init_data(telegram_id: int = 12345, username: str = "testuser") -> str:
    user = json.dumps({"id": telegram_id, "username": username, "first_name": "Test"})
    data = {"user": user, "auth_date": str(int(time.time()))}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


@pytest.fixture(autouse=True)
def reset_app_state(monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_ENDPOINTS", "true")
    get_settings.cache_clear()
    settings = get_settings()
    settings.emergency_stop = False
    settings.rate_limit_per_minute = 100_000
    settings.enable_dev_endpoints = True
    try:
        import redis as sync_redis

        sync_redis.from_url(settings.redis_url, decode_responses=True).flushdb()
    except Exception:
        pass
    yield
    settings.emergency_stop = False
    get_settings.cache_clear()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()



@pytest_asyncio.fixture
async def seed_partners(session):
    for code, name in [("mock_fiat", "Mock Fiat"), ("mock_fiat_backup", "Mock Backup")]:
        from sqlalchemy import select

        result = await session.execute(select(Partner).where(Partner.code == code))
        if not result.scalar_one_or_none():
            session.add(
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
    await session.commit()


@pytest_asyncio.fixture
async def client(engine, seed_partners, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    get_settings.cache_clear()
    from sqlalchemy import select

    from app.db import session as db_session

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        for code in ("mock_fiat", "mock_fiat_backup"):
            result = await sess.execute(select(Partner).where(Partner.code == code))
            partner = result.scalar_one_or_none()
            if partner:
                partner.circuit_breaker_state = CircuitBreakerState.CLOSED
                partner.consecutive_failures = 0
                partner.enabled = True
                partner.cooldown_until = None
        await sess.commit()

    db_session.async_session_factory = factory

    async def override_get_db():
        async with factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    from app.db.session import get_db

    app.dependency_overrides[get_db] = override_get_db

    from app.main import polling_worker

    polling_worker.stop()

    from app.partners.registry import partner_registry

    for adapter in partner_registry._adapters.values():
        if hasattr(adapter, "set_scenario"):
            adapter.set_scenario(None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def auth_headers(client):
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": make_init_data(telegram_id=999001)},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
