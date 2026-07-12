import uuid
from datetime import timedelta

from sqlalchemy import select

from app.db.base import utcnow
from app.models.quote import Quote
from tests.conftest import (
    VALID_TRON,
    authed_user,
    create_order_via_api,
    create_quote_via_api,
)


async def test_create_buy_order_with_payment_instructions(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    assert order["status"] == "AWAITING_PAYMENT"
    assert order["payment_instructions"] is not None
    pi = order["payment_instructions"]
    assert pi["masked_recipient_name"]
    assert pi["masked_account"].startswith("****")
    assert "40817810000000054321" not in str(order)  # full account never exposed
    assert order["quote_source_type"] == "MOCK"
    statuses = [e["status"] for e in order["events"]]
    assert statuses == ["QUOTE_CONFIRMED", "AWAITING_PAYMENT"]


async def test_create_sell_order_returns_deposit_address(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(
        client, headers, direction="SELL", from_asset="XMR", from_network="XMR",
        to_asset="RUB", to_network=None, amount_in="2",
    )
    order = await create_order_via_api(
        client, headers, quotes[0]["quote_id"], direction="SELL"
    )
    assert order["status"] == "AWAITING_PAYMENT"
    assert order["deposit_address"]
    assert order["deposit_network"] == "XMR"


async def test_expired_quote_rejected(client, session):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    quote = (
        await session.execute(select(Quote).where(Quote.id == quotes[0]["quote_id"]))
    ).scalar_one()
    quote.expires_at = utcnow() - timedelta(seconds=1)
    await session.commit()
    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": quote.id,
            "idempotency_key": uuid.uuid4().hex,
            "wallet_address": "4" + "A" * 94,
        },
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "quote_expired"


async def test_consumed_quote_rejected(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    await create_order_via_api(client, headers, quotes[0]["quote_id"])
    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": quotes[0]["quote_id"],
            "idempotency_key": uuid.uuid4().hex,
            "wallet_address": "4" + "A" * 94,
        },
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "quote_consumed"


async def test_idempotency_key_returns_same_order(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    key = uuid.uuid4().hex
    order1 = await create_order_via_api(
        client, headers, quotes[0]["quote_id"], idempotency_key=key
    )
    order2 = await create_order_via_api(
        client, headers, quotes[0]["quote_id"], idempotency_key=key
    )
    assert order1["id"] == order2["id"]


async def test_foreign_quote_rejected(client):
    headers_a, _ = await authed_user(client, telegram_id=301)
    headers_b, _ = await authed_user(client, telegram_id=302)
    quotes = await create_quote_via_api(client, headers_a)
    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": quotes[0]["quote_id"],
            "idempotency_key": uuid.uuid4().hex,
            "wallet_address": "4" + "A" * 94,
        },
        headers=headers_b,
    )
    assert resp.status_code == 403


async def test_invalid_wallet_rejected(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": quotes[0]["quote_id"],
            "idempotency_key": uuid.uuid4().hex,
            "wallet_address": "not-a-wallet",
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_wrong_network_wallet_rejected(client):
    """USDT TRC20 quote with an XMR-style wallet must fail."""
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(
        client, headers, to_asset="USDT", to_network="TRC20"
    )
    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": quotes[0]["quote_id"],
            "idempotency_key": uuid.uuid4().hex,
            "wallet_address": "4" + "A" * 94,
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_usdt_buy_with_tron_wallet(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(
        client, headers, to_asset="USDT", to_network="TRC20"
    )
    order = await create_order_via_api(
        client, headers, quotes[0]["quote_id"], wallet_address=VALID_TRON
    )
    assert order["status"] == "AWAITING_PAYMENT"
    assert order["wallet_address_masked"] != VALID_TRON
    assert "..." in order["wallet_address_masked"]


async def test_partner_failure_before_order(client, partners):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    alpha_quote = next(q for q in quotes if q["partner_code"] == "mock_fiat_alpha")
    partners["alpha"].set_scenario("fail_before_order")
    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": alpha_quote["quote_id"],
            "idempotency_key": uuid.uuid4().hex,
            "wallet_address": "4" + "A" * 94,
        },
        headers=headers,
    )
    assert resp.status_code == 502
    # quote is consumed; user must request a fresh quote (failover covered in e2e)


async def test_order_history_and_detail(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    listing = (await client.get("/api/v1/orders", headers=headers)).json()
    assert [o["id"] for o in listing["orders"]] == [order["id"]]
    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert detail["id"] == order["id"]
    # foreign user cannot see it
    headers_b, _ = await authed_user(client, telegram_id=303)
    resp = await client.get(f"/api/v1/orders/{order['id']}", headers=headers_b)
    assert resp.status_code == 404


async def test_dispute_order(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    # AWAITING_PAYMENT -> disputes only allowed after payment detected
    resp = await client.post(
        f"/api/v1/orders/{order['id']}/dispute",
        json={"reason": "sent money but nothing happened"},
        headers=headers,
    )
    assert resp.status_code == 409  # cannot dispute before payment detected
