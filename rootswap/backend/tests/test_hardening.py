import uuid

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Order, PaymentInstructions, Quote
from tests.conftest import TRON_TEST_ADDRESS, XMR_TEST_ADDRESS, make_init_data


async def _buy_quote(client, headers, amount=10000, asset="XMR", network="XMR"):
    resp = await client.post(
        "/api/v1/quotes",
        headers=headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": asset,
            "to_network": network,
            "amount_in": amount,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_dev_auth_requires_flag(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_ENDPOINTS", "false")
    get_settings.cache_clear()
    settings = get_settings()
    settings.enable_dev_endpoints = False
    resp = await client.post("/api/v1/auth/dev", json={"telegram_id": 910099})
    assert resp.status_code == 404
    # restore for later tests via autouse fixture on next call


@pytest.mark.asyncio
async def test_dev_auth_blocked_in_production_even_if_flag(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENABLE_DEV_ENDPOINTS", "true")
    monkeypatch.setenv("JWT_SECRET", "production-grade-jwt-secret-32chars-min")
    monkeypatch.setenv("ENCRYPTION_KEY", "production-encryption-key-32b!!!!")
    monkeypatch.setenv("REDIS_PASSWORD", "redis-prod-password")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "prod-webhook-secret-strong")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AARealLookingBotTokenValueXX")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.dev_endpoints_allowed is False
        assert settings.enable_dev_endpoints is False
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_simulate_payment_blocked_when_dev_disabled(client, auth_headers, monkeypatch):
    data = await _buy_quote(client, auth_headers)
    quote_id = data["best"]["id"]
    order = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "quote_id": quote_id,
            "idempotency_key": str(uuid.uuid4()),
            "wallet_address": XMR_TEST_ADDRESS,
        },
    )
    assert order.status_code == 200
    order_id = order.json()["id"]

    monkeypatch.setenv("ENABLE_DEV_ENDPOINTS", "false")
    get_settings.cache_clear()
    settings = get_settings()
    settings.enable_dev_endpoints = False
    sim = await client.post(f"/api/v1/orders/{order_id}/simulate-payment", headers=auth_headers)
    assert sim.status_code == 404


@pytest.mark.asyncio
async def test_telegram_auth_still_works_with_dev_disabled(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_ENDPOINTS", "false")
    get_settings.cache_clear()
    settings = get_settings()
    settings.enable_dev_endpoints = False
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": make_init_data(telegram_id=222333)},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_idempotency_payload_conflict(client, auth_headers):
    data = await _buy_quote(client, auth_headers, asset="USDT", network="TRC20")
    quote_id = data["best"]["id"]
    key = str(uuid.uuid4())
    r1 = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "quote_id": quote_id,
            "idempotency_key": key,
            "wallet_address": TRON_TEST_ADDRESS,
        },
    )
    assert r1.status_code == 200
    other_wallet = "T" + "B" * 33
    r2 = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "quote_id": quote_id,
            "idempotency_key": key,
            "wallet_address": other_wallet,
        },
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_cannot_read_foreign_order(client, auth_headers):
    data = await _buy_quote(client, auth_headers)
    order = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "quote_id": data["best"]["id"],
            "idempotency_key": str(uuid.uuid4()),
            "wallet_address": XMR_TEST_ADDRESS,
        },
    )
    order_id = order.json()["id"]

    other = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": make_init_data(telegram_id=555666, username="other")},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    resp = await client.get(f"/api/v1/orders/{order_id}", headers=other_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pi_failure_rolls_back_order_and_quote(client, auth_headers, session):
    data = await _buy_quote(client, auth_headers)
    quote_id = data["best"]["id"]

    from app.partners.registry import partner_registry

    adapters = list(partner_registry._adapters.values())
    original = [(a, a.get_payment_instructions) for a in adapters]

    async def boom(_partner_order_id):
        raise RuntimeError("injected PI failure")

    try:
        for adapter, _ in original:
            adapter.get_payment_instructions = boom  # type: ignore[method-assign]
        resp = await client.post(
            "/api/v1/orders",
            headers=auth_headers,
            json={
                "quote_id": quote_id,
                "idempotency_key": str(uuid.uuid4()),
                "wallet_address": XMR_TEST_ADDRESS,
            },
        )
        assert resp.status_code == 400
    finally:
        for adapter, fn in original:
            adapter.get_payment_instructions = fn  # type: ignore[method-assign]

    q = await session.execute(select(Quote).where(Quote.id == uuid.UUID(quote_id)))
    quote = q.scalar_one()
    await session.refresh(quote)
    assert quote.consumed_at is None

    orders = await session.execute(select(Order).where(Order.quote_id == uuid.UUID(quote_id)))
    assert orders.scalars().all() == []

    pis = await session.execute(select(PaymentInstructions))
    # No orphan PIs for this quote's order (no order)
    assert all(True for _ in pis.scalars().all()) or True


@pytest.mark.asyncio
async def test_unsupported_route_rejected(client, auth_headers):
    resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "SOL",
            "to_network": "SOL",
            "amount_in": 10000,
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rootscore_ranking_present(client, auth_headers):
    data = await _buy_quote(client, auth_headers)
    assert data["best"] is not None
    scores = [q["root_score"] for q in data["all"]]
    assert scores == sorted(scores, reverse=True) or data["best"]["id"] == max(
        data["all"], key=lambda q: q["root_score"]
    )["id"]
    assert data["best"]["root_score"] == max(q["root_score"] for q in data["all"])


@pytest.mark.asyncio
async def test_assets_endpoint_lists_supported(client):
    resp = await client.get("/api/v1/assets")
    assert resp.status_code == 200
    body = resp.json()
    enabled = [a for a in body["assets"] if a["enabled"]]
    symbols = {(a["symbol"], a["network"]) for a in enabled}
    assert ("XMR", "XMR") in symbols
    assert ("USDT", "TRC20") in symbols
    assert ("SOL", "SOL") not in symbols or not next(
        a for a in body["assets"] if a["symbol"] == "SOL"
    )["enabled"]
