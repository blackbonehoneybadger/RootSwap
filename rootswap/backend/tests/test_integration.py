import uuid

import pytest
from sqlalchemy import select

from app.core.enums import CircuitBreakerState, OrderDirection
from app.models import LedgerEntry, Partner, ReferralReward
from app.services.quote_engine import QuoteEngine
from tests.conftest import TRON_TEST_ADDRESS, XMR_TEST_ADDRESS, make_init_data


@pytest.mark.asyncio
async def test_telegram_auth(client):
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": make_init_data(telegram_id=111222)},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_create_quote_rub_xmr(client, auth_headers):
    resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
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
    assert resp.status_code == 200
    data = resp.json()
    assert data["best"] is not None
    assert data["best"]["to_asset"] == "XMR"
    assert data["best"]["quote_source_type"] == "MOCK"


@pytest.mark.asyncio
async def test_create_order(client, auth_headers):
    quote_resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "XMR",
            "to_network": "XMR",
            "amount_in": 10000,
        },
    )
    quote_id = quote_resp.json()["best"]["id"]
    order_resp = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "quote_id": quote_id,
            "idempotency_key": str(uuid.uuid4()),
            "wallet_address": XMR_TEST_ADDRESS,
        },
    )
    assert order_resp.status_code == 200
    order = order_resp.json()
    assert order["status"] == "AWAITING_PAYMENT"
    assert order["payment_instructions"] is not None
    pi = order["payment_instructions"]
    assert pi["amount"] == 10000.0
    # MOCK reveal for demo copy-paste
    assert pi["sbp_phone"] == "+79001234567"
    assert pi["account_number"]
    assert pi["payment_comment"]


@pytest.mark.asyncio
async def test_buy_requires_wallet(client, auth_headers):
    quote_resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "XMR",
            "to_network": "XMR",
            "amount_in": 10000,
        },
    )
    quote_id = quote_resp.json()["best"]["id"]
    order_resp = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"quote_id": quote_id, "idempotency_key": str(uuid.uuid4())},
    )
    assert order_resp.status_code == 400


@pytest.mark.asyncio
async def test_simulate_payment_completes_mock_order(client, auth_headers):
    quote_resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "XMR",
            "to_network": "XMR",
            "amount_in": 12000,
        },
    )
    quote_id = quote_resp.json()["best"]["id"]
    order_resp = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "quote_id": quote_id,
            "idempotency_key": str(uuid.uuid4()),
            "wallet_address": XMR_TEST_ADDRESS,
        },
    )
    order_id = order_resp.json()["id"]
    sim = await client.post(
        f"/api/v1/orders/{order_id}/simulate-payment",
        headers=auth_headers,
    )
    assert sim.status_code == 200, sim.text
    assert sim.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_dev_auth(client):
    resp = await client.post(
        "/api/v1/auth/dev",
        json={"telegram_id": 910001, "username": "browser_dev"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_idempotency(client, auth_headers):
    quote_resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "USDT",
            "to_network": "TRC20",
            "amount_in": 5000,
        },
    )
    quote_id = quote_resp.json()["best"]["id"]
    key = str(uuid.uuid4())
    body = {
        "quote_id": quote_id,
        "idempotency_key": key,
        "wallet_address": TRON_TEST_ADDRESS,
    }
    r1 = await client.post("/api/v1/orders", headers=auth_headers, json=body)
    r2 = await client.post("/api/v1/orders", headers=auth_headers, json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_webhook_success(client, auth_headers, session):
    quote_resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "XMR",
            "to_network": "XMR",
            "amount_in": 10000,
        },
    )
    quote_id = quote_resp.json()["best"]["id"]
    order_resp = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "quote_id": quote_id,
            "idempotency_key": str(uuid.uuid4()),
            "wallet_address": XMR_TEST_ADDRESS,
        },
    )
    order = order_resp.json()
    partner_order_id = order["partner_order_id"]

    from app.partners.mock_fiat import MockFiatPartnerAdapter

    adapter = MockFiatPartnerAdapter()
    for status in ["payment_detected", "payment_confirming", "processing", "payout_sent", "completed"]:
        body, headers_wh = adapter.build_webhook_payload(partner_order_id, status)
        resp = await client.post(
            "/api/v1/webhooks/partners/mock_fiat",
            content=body,
            headers=headers_wh,
        )
        assert resp.status_code == 200

    detail = await client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers)
    assert detail.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_duplicate_webhook_no_duplicate_ledger(client, auth_headers, session):
    quote_resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "BTC",
            "to_network": "BTC",
            "amount_in": 10000,
        },
    )
    quote_id = quote_resp.json()["best"]["id"]
    order_resp = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "quote_id": quote_id,
            "idempotency_key": str(uuid.uuid4()),
            "wallet_address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
        },
    )
    order = order_resp.json()
    from app.partners.mock_fiat import MockFiatPartnerAdapter

    adapter = MockFiatPartnerAdapter()
    for status in ["payment_detected", "payment_confirming", "processing", "payout_sent", "completed"]:
        body, headers_wh = adapter.build_webhook_payload(order["partner_order_id"], status)
        await client.post("/api/v1/webhooks/partners/mock_fiat", content=body, headers=headers_wh)

    body, headers_wh = adapter.build_webhook_payload(
        order["partner_order_id"], "completed", external_event_id="dup-event-1"
    )
    await client.post("/api/v1/webhooks/partners/mock_fiat", content=body, headers=headers_wh)
    r2 = await client.post("/api/v1/webhooks/partners/mock_fiat", content=body, headers=headers_wh)
    assert r2.json()["status"] == "duplicate"

    result = await session.execute(select(LedgerEntry).where(LedgerEntry.order_id == uuid.UUID(order["id"])))
    entries = result.scalars().all()
    posting_keys = [e.posting_key for e in entries]
    assert len(posting_keys) == len(set(posting_keys))


@pytest.mark.asyncio
async def test_invalid_webhook_signature(client):
    resp = await client.post(
        "/api/v1/webhooks/partners/mock_fiat",
        json={"event_id": "x", "partner_order_id": "y", "status": "completed"},
        headers={"X-Mock-Signature": "bad", "X-Mock-Timestamp": "123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_emergency_stop(client, auth_headers):
    await client.post("/api/v1/admin/emergency-stop", headers={"X-Admin-Key": "dev-admin-key"})
    quote_resp = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "XMR",
            "to_network": "XMR",
            "amount_in": 1000,
        },
    )
    quote_id = quote_resp.json()["best"]["id"]
    order_resp = await client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"quote_id": quote_id, "idempotency_key": str(uuid.uuid4()), "wallet_address": XMR_TEST_ADDRESS},
    )
    assert order_resp.status_code == 503
    await client.delete("/api/v1/admin/emergency-stop", headers={"X-Admin-Key": "dev-admin-key"})


@pytest.mark.asyncio
async def test_rbac_denied(client):
    resp = await client.get("/api/v1/admin/orders", headers={"X-Admin-Key": "wrong-key"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ledger_reconciliation(client, auth_headers):
    resp = await client.get(
        "/api/v1/admin/ledger/reconciliation",
        headers={"X-Admin-Key": "dev-admin-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["balanced"] is True


@pytest.mark.asyncio
async def test_circuit_breaker_open_excludes_partner(session, seed_partners):
    result = await session.execute(select(Partner).where(Partner.code == "mock_fiat"))
    partner = result.scalar_one()
    partner.circuit_breaker_state = CircuitBreakerState.OPEN
    backup = await session.execute(select(Partner).where(Partner.code == "mock_fiat_backup"))
    backup_partner = backup.scalar_one()
    backup_partner.circuit_breaker_state = CircuitBreakerState.OPEN
    await session.commit()
    engine = QuoteEngine()
    from app.models import User

    user = User(telegram_id=555, referral_code="REF555")
    session.add(user)
    await session.commit()
    quotes_result = await engine.create_quotes(
        session, user, OrderDirection.BUY, "RUB", None, "XMR", "XMR", 10000
    )
    assert quotes_result["all"] == []


@pytest.mark.asyncio
async def test_referral_reward_once(client, session):
    ref_resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": make_init_data(telegram_id=888001)},
    )
    referrer_token = ref_resp.json()["access_token"]
    referrer_headers = {"Authorization": f"Bearer {referrer_token}"}
    stats = await client.get("/api/v1/referral/stats", headers=referrer_headers)
    ref_code = stats.json()["referral_code"]

    user_resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": make_init_data(telegram_id=888002), "referral_code": ref_code},
    )
    user_headers = {"Authorization": f"Bearer {user_resp.json()['access_token']}"}

    quote_resp = await client.post(
        "/api/v1/quotes",
        headers=user_headers,
        json={"direction": "BUY", "from_asset": "RUB", "to_asset": "XMR", "to_network": "XMR", "amount_in": 10000},
    )
    quote_id = quote_resp.json()["best"]["id"]
    order_resp = await client.post(
        "/api/v1/orders",
        headers=user_headers,
        json={"quote_id": quote_id, "idempotency_key": str(uuid.uuid4()), "wallet_address": XMR_TEST_ADDRESS},
    )
    order = order_resp.json()
    from app.partners.mock_fiat import MockFiatPartnerAdapter

    adapter = MockFiatPartnerAdapter()
    for status in ["payment_detected", "payment_confirming", "processing", "payout_sent", "completed"]:
        body, headers_wh = adapter.build_webhook_payload(order["partner_order_id"], status)
        await client.post("/api/v1/webhooks/partners/mock_fiat", content=body, headers=headers_wh)

    rewards = await session.execute(select(ReferralReward))
    reward_list = rewards.scalars().all()
    assert len(reward_list) == 1
