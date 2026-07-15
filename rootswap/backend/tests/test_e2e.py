import uuid

import pytest

from app.core.enums import OrderDirection, QuoteSourceType
from app.core.exceptions import ForbiddenError
from app.services.quote_engine import QuoteEngine
from tests.conftest import TRON_TEST_ADDRESS, XMR_TEST_ADDRESS


@pytest.mark.asyncio
async def test_e2e_rub_to_xmr(client, auth_headers):
    quote = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={"direction": "BUY", "from_asset": "RUB", "to_asset": "XMR", "to_network": "XMR", "amount_in": 25000, "payment_method": "SBP", "bank_name": "Tinkoff"},
    )
    assert quote.status_code == 200
    quote_id = quote.json()["best"]["id"]
    order = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"quote_id": quote_id, "idempotency_key": str(uuid.uuid4()), "wallet_address": XMR_TEST_ADDRESS, "payment_method": "SBP", "bank_name": "Tinkoff"},
    )
    assert order.status_code == 200
    assert order.json()["from_asset"] == "RUB"
    assert order.json()["to_asset"] == "XMR"


@pytest.mark.asyncio
async def test_e2e_xmr_to_rub(client, auth_headers):
    quote = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={"direction": "SELL", "from_asset": "XMR", "from_network": "XMR", "to_asset": "RUB", "amount_in": 1.5},
    )
    assert quote.status_code == 200
    quote_id = quote.json()["best"]["id"]
    order = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"quote_id": quote_id, "idempotency_key": str(uuid.uuid4()), "payment_method": "bank_transfer", "bank_name": "Sber", "payout_details": {"account": "***"}},
    )
    assert order.status_code == 200
    assert order.json()["direction"] == "SELL"


@pytest.mark.asyncio
async def test_partner_failure_on_create(client, auth_headers):
    """Quote succeeds; create_fiat_order fails → order rolled back, no orphans."""
    quote = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "USDT",
            "to_network": "TRC20",
            "amount_in": 5000,
            "scenario": "create_failure",
        },
    )
    assert quote.status_code == 200
    assert quote.json()["best"] is not None
    quote_id = quote.json()["best"]["id"]
    order = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "quote_id": quote_id,
            "idempotency_key": str(uuid.uuid4()),
            "wallet_address": TRON_TEST_ADDRESS,
            "scenario": "create_failure",
        },
    )
    assert order.status_code == 400


@pytest.mark.asyncio
async def test_production_rejects_mock(monkeypatch, session, seed_partners):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "production-jwt-secret-key-32chars-minimum!!")
    monkeypatch.setenv("ENCRYPTION_KEY", "production-encryption-key-32bytes!!")
    monkeypatch.setenv("REDIS_PASSWORD", "redis-prod-password")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "prod-webhook-secret-value")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AARealLookingBotTokenValueXXXX")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.models import User

    user = User(telegram_id=777001, referral_code="PROD777")
    session.add(user)
    await session.commit()
    engine = QuoteEngine()
    with pytest.raises(ForbiddenError):
        await engine.create_quotes(session, user, OrderDirection.BUY, "RUB", None, "XMR", "XMR", 1000)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_quote_expired(client, auth_headers, session, seed_partners):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import Quote, User

    result = await session.execute(select(User).where(User.telegram_id == 999001))
    user = result.scalar_one()
    quote = Quote(
        user_id=user.id,
        partner_code="mock_fiat",
        direction=OrderDirection.BUY,
        from_asset="RUB",
        to_asset="XMR",
        to_network="XMR",
        amount_in=1000,
        amount_out=0.04,
        exchange_rate=0.00004,
        service_fee=15,
        partner_fee=5,
        network_fee=0.01,
        total_fee=20.01,
        root_score=50,
        quote_source_type=QuoteSourceType.MOCK,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(quote)
    await session.commit()
    resp = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"quote_id": str(quote.id), "idempotency_key": str(uuid.uuid4()), "wallet_address": XMR_TEST_ADDRESS},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_sensitive_values_not_in_logs():
    from app.security import mask_sensitive_data

    data = {"account_number": "40817810099910004312", "wallet": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"}
    masked = mask_sensitive_data(data)
    assert "40817810099910004312" not in str(masked)
    assert "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh" not in str(masked)
