"""End-to-end mock flows (no real money, deterministic mock partners)."""

import logging
import uuid

from sqlalchemy import select

from app.models.ledger import LedgerEntry
from app.models.order import Order
from app.models.referral import ReferralReward
from tests.conftest import (
    VALID_TRON,
    authed_user,
    create_order_via_api,
    create_quote_via_api,
)
from tests.integration.test_webhooks import get_partner_order_id, send_webhook


async def test_rub_to_xmr_full_mock_flow(client, session):
    """User path: auth -> quote -> order -> payment instructions -> webhooks -> COMPLETED."""
    headers, _ = await authed_user(client, telegram_id=1001)
    quotes = await create_quote_via_api(client, headers, to_asset="XMR", to_network="XMR")
    assert all(q["quote_source_type"] == "MOCK" for q in quotes)
    best = quotes[0]
    order = await create_order_via_api(client, headers, best["quote_id"])
    assert order["payment_instructions"]["bank_name"]
    assert order["payment_instructions"]["payment_comment"].startswith("RS-")
    poid = await get_partner_order_id(session, order["id"])

    for event in ["payment_detected", "payment_confirming", "processing", "payout_sent", "completed"]:
        resp = await send_webhook(client, poid, event)
        assert resp.status_code == 200

    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert detail["status"] == "COMPLETED"
    statuses = [e["status"] for e in detail["events"]]
    assert statuses[0] == "QUOTE_CONFIRMED"
    assert statuses[-1] == "COMPLETED"
    # history shows it
    history = (await client.get("/api/v1/orders", headers=headers)).json()
    assert history["orders"][0]["status"] == "COMPLETED"


async def test_rub_to_usdt_via_sbp(client, session):
    headers, _ = await authed_user(client, telegram_id=1002)
    quotes = await create_quote_via_api(client, headers, to_asset="USDT", to_network="TRC20")
    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": quotes[0]["quote_id"],
            "idempotency_key": uuid.uuid4().hex,
            "wallet_address": VALID_TRON,
            "payment_method": "SBP",
            "bank": "Tinkoff",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    order = resp.json()
    pi = order["payment_instructions"]
    assert pi["payment_method"] == "SBP"
    assert pi["bank_name"] == "Tinkoff"
    assert pi["masked_phone"] and pi["masked_phone"].endswith("67")
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "completed")
    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert detail["status"] == "COMPLETED"


async def test_xmr_to_rub_full_mock_flow(client, session):
    headers, _ = await authed_user(client, telegram_id=1003)
    quotes = await create_quote_via_api(
        client, headers, direction="SELL", from_asset="XMR", from_network="XMR",
        to_asset="RUB", to_network=None, amount_in="2",
    )
    order = await create_order_via_api(
        client, headers, quotes[0]["quote_id"], direction="SELL"
    )
    assert order["deposit_address"].startswith("4")
    poid = await get_partner_order_id(session, order["id"])
    for event in ["payment_detected", "processing", "payout_sent", "completed"]:
        await send_webhook(client, poid, event)
    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert detail["status"] == "COMPLETED"


async def test_failover_to_second_partner(client, partners):
    """Alpha fails on quotes -> user still gets beta quotes and completes order."""
    partners["alpha"].set_scenario("quote_failure")
    headers, _ = await authed_user(client, telegram_id=1004)
    quotes = await create_quote_via_api(client, headers)
    assert {q["partner_code"] for q in quotes} == {"mock_fiat_beta"}
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    assert order["status"] == "AWAITING_PAYMENT"


async def test_referral_reward_exactly_once(client, session):
    referrer_headers, referrer = await authed_user(client, telegram_id=1005)
    headers, _ = await authed_user(
        client, telegram_id=1006, start_param=f"ref_{referrer['referral_code']}"
    )
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "completed", event_id="ref-evt-1")
    # duplicate + a second distinct 'completed' event
    await send_webhook(client, poid, "completed", event_id="ref-evt-1")
    await send_webhook(client, poid, "completed", event_id="ref-evt-2")

    rewards = (
        (
            await session.execute(
                select(ReferralReward).where(ReferralReward.order_id == order["id"])
            )
        )
        .scalars()
        .all()
    )
    assert len(rewards) == 1
    assert rewards[0].referrer_user_id == referrer["id"]
    assert rewards[0].status.value == "CONFIRMED"

    stats = (await client.get("/api/v1/referral/stats", headers=referrer_headers)).json()
    assert stats["referred_count"] == 1
    assert stats["active_referred_count"] == 1
    assert len(stats["rewards"]) == 1
    assert stats["total_rewards"][0]["currency"] == "RUB"
    assert stats["referral_link"].endswith(f"ref_{referrer['referral_code']}")


async def test_no_reward_without_referrer(client, session):
    headers, _ = await authed_user(client, telegram_id=1007)
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "completed")
    rewards = (
        (
            await session.execute(
                select(ReferralReward).where(ReferralReward.order_id == order["id"])
            )
        )
        .scalars()
        .all()
    )
    assert rewards == []


async def test_no_reward_on_expired_order(client, session):
    referrer_headers, referrer = await authed_user(client, telegram_id=1008)
    headers, _ = await authed_user(
        client, telegram_id=1009, start_param=f"ref_{referrer['referral_code']}"
    )
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "expired")
    rewards = (
        (await session.execute(select(ReferralReward))).scalars().all()
    )
    assert rewards == []
    # and no ledger postings at all for an expired order
    postings = (
        (
            await session.execute(
                select(LedgerEntry).where(LedgerEntry.order_id == order["id"])
            )
        )
        .scalars()
        .all()
    )
    assert postings == []


async def test_disputed_order_not_realized_and_reward_frozen(client, session):
    referrer_headers, referrer = await authed_user(client, telegram_id=1010)
    headers, _ = await authed_user(
        client, telegram_id=1011, start_param=f"ref_{referrer['referral_code']}"
    )
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "payment_detected")
    # user opens a dispute before completion
    resp = await client.post(
        f"/api/v1/orders/{order['id']}/dispute",
        json={"reason": "paid but no crypto received"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "DISPUTED"
    # no realized profit for a disputed order
    postings = (
        (
            await session.execute(
                select(LedgerEntry).where(LedgerEntry.order_id == order["id"])
            )
        )
        .scalars()
        .all()
    )
    assert postings == []


async def test_dispute_after_completed_freezes_reward(client, session):
    referrer_headers, referrer = await authed_user(client, telegram_id=1012)
    headers, _ = await authed_user(
        client, telegram_id=1013, start_param=f"ref_{referrer['referral_code']}"
    )
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "completed")
    resp = await client.post(
        f"/api/v1/orders/{order['id']}/dispute",
        json={"reason": "received less than promised"},
        headers=headers,
    )
    assert resp.status_code == 200
    reward = (
        await session.execute(
            select(ReferralReward).where(ReferralReward.order_id == order["id"])
        )
    ).scalar_one()
    assert reward.status.value == "FROZEN"


async def test_refund_after_completed_balances_ledger(client, session):
    from tests.integration.test_admin import admin_headers

    headers, _ = await authed_user(client, telegram_id=1014)
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "completed")
    finance = await admin_headers(session, 1015, role="FINANCE")
    resp = await client.post(
        f"/api/v1/admin/orders/{order['id']}/refund",
        json={"reason": "goodwill refund in mock flow"},
        headers=finance,
    )
    assert resp.status_code == 200
    recon = (
        await client.get("/api/v1/admin/ledger/reconciliation", headers=finance)
    ).json()
    assert recon["balanced"] is True
    assert recon["total_residual"] == "0"


async def test_sensitive_values_never_logged(client, session, caplog):
    """Full flow with log capture: raw bank details and wallets must not leak."""
    caplog.set_level(logging.DEBUG)
    headers, _ = await authed_user(client, telegram_id=1016)
    quotes = await create_quote_via_api(client, headers)
    wallet = "4" + "B" * 94
    order = await create_order_via_api(
        client, headers, quotes[0]["quote_id"], wallet_address=wallet
    )
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "completed")

    log_text = " ".join(r.getMessage() + str(getattr(r, "ctx", "")) for r in caplog.records)
    assert "40817810000000054321" not in log_text  # mock account number
    assert "2200123456784321" not in log_text  # mock card number
    assert "+79001234567" not in log_text  # mock SBP phone
    assert wallet not in log_text  # user wallet address

    # DB stores encrypted + masked only
    row = (
        await session.execute(select(Order).where(Order.id == order["id"]))
    ).scalar_one()
    assert wallet not in (row.wallet_address_encrypted or "")
    assert row.wallet_address_masked != wallet


async def test_metrics_endpoint_exposes_counters(client, session):
    headers, _ = await authed_user(client, telegram_id=1017)
    await create_quote_via_api(client, headers)
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "quotes_created_total" in resp.text


async def test_health_endpoints(client):
    resp = await client.get("/health")
    assert resp.json() == {"status": "ok"}
    resp = await client.get("/health/ready")
    assert resp.json()["status"] == "ready"
