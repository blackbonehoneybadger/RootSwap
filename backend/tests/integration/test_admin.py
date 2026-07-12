from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.conftest import (
    auth_headers,
    authed_user,
    create_order_via_api,
    create_quote_via_api,
    create_user,
)
from tests.integration.test_webhooks import get_partner_order_id, send_webhook


async def admin_headers(session, telegram_id=900, role="ADMIN"):
    user = await create_user(session, telegram_id)
    return auth_headers(user, role=role)


async def test_rbac_denies_regular_user(client, session):
    headers, _ = await authed_user(client)
    resp = await client.get("/api/v1/admin/orders", headers=headers)
    assert resp.status_code == 403


async def test_rbac_denies_low_role_for_finance_endpoint(client, session):
    support = await admin_headers(session, 901, role="SUPPORT")
    resp = await client.get("/api/v1/admin/ledger/reconciliation", headers=support)
    assert resp.status_code == 403


async def test_rbac_allows_support_to_list_orders(client, session):
    support = await admin_headers(session, 902, role="SUPPORT")
    resp = await client.get("/api/v1/admin/orders", headers=support)
    assert resp.status_code == 200


async def test_admin_actions_write_audit_log(client, session):
    admin = await admin_headers(session, 903, role="ADMIN")
    resp = await client.get("/api/v1/admin/partners", headers=admin)
    assert resp.status_code == 200
    audits = (
        (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "admin.partners.list")
            )
        )
        .scalars()
        .all()
    )
    assert audits


async def test_admin_transition(client, session):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    ops = await admin_headers(session, 904, role="OPERATIONS")
    resp = await client.post(
        f"/api/v1/admin/orders/{order['id']}/transition",
        json={"target_status": "PAYMENT_DETECTED", "reason": "manual verification ok"},
        headers=ops,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PAYMENT_DETECTED"
    # forbidden transition -> 409 + audit
    resp = await client.post(
        f"/api/v1/admin/orders/{order['id']}/transition",
        json={"target_status": "REFUNDED", "reason": "should not be allowed"},
        headers=ops,
    )
    assert resp.status_code == 409


async def test_admin_refund_after_completed(client, session):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "completed")
    finance = await admin_headers(session, 905, role="FINANCE")
    resp = await client.post(
        f"/api/v1/admin/orders/{order['id']}/refund",
        json={"reason": "customer complaint upheld"},
        headers=finance,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REFUNDED"
    recon = await client.get("/api/v1/admin/ledger/reconciliation", headers=finance)
    assert recon.json()["balanced"] is True


async def test_partner_enable_disable_and_reset(client, session):
    ops = await admin_headers(session, 906, role="OPERATIONS")
    resp = await client.post(
        "/api/v1/admin/partners/mock_fiat_alpha/disable",
        json={"reason": "maintenance window"},
        headers=ops,
    )
    assert resp.status_code == 200 and resp.json()["enabled"] is False
    resp = await client.post(
        "/api/v1/admin/partners/mock_fiat_alpha/enable", headers=ops
    )
    assert resp.status_code == 200 and resp.json()["enabled"] is True
    resp = await client.post(
        "/api/v1/admin/partners/mock_fiat_alpha/reset-circuit", headers=ops
    )
    assert resp.status_code == 200
    assert resp.json()["circuit_breaker_state"] == "CLOSED"


async def test_emergency_stop_blocks_new_orders(client, session):
    headers, _ = await authed_user(client)
    admin = await admin_headers(session, 907, role="ADMIN")
    quotes_before_stop = await create_quote_via_api(client, headers)
    resp = await client.post(
        "/api/v1/admin/emergency-stop",
        json={"reason": "incident response drill"},
        headers=admin,
    )
    assert resp.status_code == 200
    # quotes blocked
    resp = await client.post(
        "/api/v1/quotes",
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "XMR",
            "to_network": "XMR",
            "amount_in": "50000",
        },
        headers=headers,
    )
    assert resp.status_code == 503
    # order creation blocked even with a quote obtained before the stop
    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": quotes_before_stop[0]["quote_id"],
            "idempotency_key": "emergency-stop-order-block",
            "wallet_address": "4" + "A" * 94,
        },
        headers=headers,
    )
    assert resp.status_code == 503
    # clear
    resp = await client.request("DELETE", "/api/v1/admin/emergency-stop", headers=admin)
    assert resp.status_code == 200
    quotes = await create_quote_via_api(client, headers)
    assert quotes


async def test_admin_transition_to_completed_posts_ledger(client, session):
    from app.models.ledger import LedgerEntry

    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    order = await create_order_via_api(client, headers, quotes[0]["quote_id"])
    ops = await admin_headers(session, 910, role="OPERATIONS")
    for status in (
        "PAYMENT_DETECTED",
        "PAYMENT_CONFIRMING",
        "PROCESSING",
        "PAYOUT_SENT",
        "COMPLETED",
    ):
        resp = await client.post(
            f"/api/v1/admin/orders/{order['id']}/transition",
            json={"target_status": status, "reason": "manual completion in mock"},
            headers=ops,
        )
        assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COMPLETED"
    postings = (
        (
            await session.execute(
                select(LedgerEntry).where(LedgerEntry.order_id == order["id"])
            )
        )
        .scalars()
        .all()
    )
    assert any(p.posting_key.endswith("gross_service_fee") for p in postings)


async def test_emergency_stop_requires_admin_role(client, session):
    finance = await admin_headers(session, 908, role="FINANCE")
    resp = await client.post(
        "/api/v1/admin/emergency-stop",
        json={"reason": "trying without admin role"},
        headers=finance,
    )
    assert resp.status_code == 403


async def test_admin_webhooks_and_risk_flags_lists(client, session):
    support = await admin_headers(session, 909, role="SUPPORT")
    resp = await client.get("/api/v1/admin/webhooks", headers=support)
    assert resp.status_code == 200
    resp = await client.get("/api/v1/admin/risk-flags", headers=support)
    assert resp.status_code == 200
