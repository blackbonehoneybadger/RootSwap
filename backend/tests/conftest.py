import json
import os
import time
import uuid
from decimal import Decimal
from urllib.parse import urlencode

# Test environment must be configured before app modules are imported.
TEST_BOT_TOKEN = "1234567:test-bot-token-for-hmac"
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", TEST_BOT_TOKEN)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-which-is-long-enough-000")
os.environ.setdefault(
    "ENCRYPTION_KEY",
    "iYKWBnhWXfX5fiVcSWbBKwJMNKpvAS5lV8ykBonQksc=",
)
os.environ.setdefault("PARTNER_WEBHOOK_SECRET", "test-webhook-secret-which-is-long-enough")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("POLLING_ENABLED", "false")
os.environ.setdefault("NOTIFICATIONS_ENABLED", "false")
# ASGI test client speaks http://; Secure cookies would never round-trip.
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_SAMESITE", "lax")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db import session as db_session
from app.db.base import Base
from app.main import create_app
from app.models.user import User
from app.observability.metrics import metrics
from app.partners.mock_crypto import MockCryptoPartnerAdapter
from app.partners.mock_fiat import MockFiatPartnerAdapter, sign_mock_webhook
from app.partners.registry import registry
from app.security.jwt import create_access_token
from app.security.telegram import compute_init_data_hash
from app.services.referral import generate_referral_code


@pytest.fixture(autouse=True)
def _reset_state():
    get_settings.cache_clear()
    metrics.reset()
    registry._adapters.clear()
    yield
    registry._adapters.clear()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def engine(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    db_session.set_session_factory(factory)
    return factory


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def partners(session_factory):
    """Register fresh mock partners and sync their DB rows."""
    alpha = MockFiatPartnerAdapter()
    beta = MockFiatPartnerAdapter(
        code="mock_fiat_beta", name="Mock Fiat Beta",
        fee_percent=Decimal("0.6"), latency_score_minutes=8,
    )
    crypto = MockCryptoPartnerAdapter()
    registry.register_adapter(alpha)
    registry.register_adapter(beta)
    registry.register_adapter(crypto)
    async with session_factory() as sess:
        await registry.sync_partner_rows(sess)
        await registry.disable_partner(sess, "mock_crypto", "reference adapter")
    return {"alpha": alpha, "beta": beta, "crypto": crypto}


@pytest_asyncio.fixture
async def client(session_factory, partners):
    app = create_app()

    async def override_get_db():
        async with session_factory() as sess:
            yield sess

    app.dependency_overrides[db_session.get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def make_init_data(
    telegram_id: int = 100500,
    username: str = "testuser",
    first_name: str = "Test",
    start_param: str | None = None,
    bot_token: str = TEST_BOT_TOKEN,
) -> str:
    pairs = {
        "user": json.dumps(
            {"id": telegram_id, "username": username, "first_name": first_name}
        ),
        "auth_date": str(int(time.time())),
    }
    if start_param:
        pairs["start_param"] = start_param
    pairs["hash"] = compute_init_data_hash(pairs, bot_token)
    return urlencode(pairs)


async def create_user(session, telegram_id: int = 100500, **kwargs) -> User:
    user = User(
        telegram_id=telegram_id,
        username=kwargs.get("username", f"user{telegram_id}"),
        first_name=kwargs.get("first_name", "Test"),
        referral_code=kwargs.get("referral_code", generate_referral_code()),
        referred_by_user_id=kwargs.get("referred_by_user_id"),
    )
    session.add(user)
    await session.commit()
    return user


def auth_headers(user: User, role: str | None = None) -> dict:
    token = create_access_token(user.id, user.telegram_id, role)
    return {"Authorization": f"Bearer {token}"}


def make_webhook_request(
    partner_order_id: str,
    event_type: str,
    event_id: str | None = None,
    timestamp: int | None = None,
    secret: str | None = None,
) -> dict:
    payload = {
        "event_id": event_id or uuid.uuid4().hex,
        "event_type": event_type,
        "partner_order_id": partner_order_id,
    }
    body = json.dumps(payload).encode()
    ts = str(timestamp if timestamp is not None else int(time.time()))
    signature = sign_mock_webhook(body, ts, secret)
    return {
        "content": body,
        "headers": {
            "X-Signature": signature,
            "X-Timestamp": ts,
            "Content-Type": "application/json",
        },
        "event_id": payload["event_id"],
    }


async def authed_user(client: AsyncClient, telegram_id: int = 100500, start_param=None):
    """Register through the real auth endpoint, return (headers, user_payload)."""
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": make_init_data(telegram_id=telegram_id, start_param=start_param)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def create_quote_via_api(
    client: AsyncClient,
    headers: dict,
    direction: str = "BUY",
    from_asset: str = "RUB",
    from_network=None,
    to_asset: str = "XMR",
    to_network: str = "XMR",
    amount_in: str = "50000",
):
    resp = await client.post(
        "/api/v1/quotes",
        json={
            "direction": direction,
            "from_asset": from_asset,
            "from_network": from_network,
            "to_asset": to_asset,
            "to_network": to_network,
            "amount_in": amount_in,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["quotes"]


# synthetic address: correct length (95), prefix (4) and Monero base58 charset
VALID_XMR = "4" + "AdUndXH2cfufTMvppY6JwXNouMBzSkbLYfpAV5Usx3skxNgYeYT" .ljust(94, "z")
VALID_BTC_LEGACY = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
VALID_BTC_BECH32 = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
VALID_TRON = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


async def create_order_via_api(
    client: AsyncClient,
    headers: dict,
    quote_id: str,
    direction: str = "BUY",
    wallet_address: str | None = None,
    idempotency_key: str | None = None,
):
    body = {
        "quote_id": quote_id,
        "idempotency_key": idempotency_key or uuid.uuid4().hex,
    }
    if direction == "BUY":
        body["wallet_address"] = wallet_address or VALID_XMR
    else:
        body["payout_details"] = {
            "payment_method": "SBP",
            "bank": "Sber",
            "account": "+79001112233",
        }
    resp = await client.post("/api/v1/orders", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()
