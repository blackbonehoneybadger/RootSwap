import time

from sqlalchemy import select

from app.models.ledger import LedgerEntry
from app.models.order import Order
from app.models.webhook_event import WebhookEvent
from tests.conftest import (
    authed_user,
    create_order_via_api,
    create_quote_via_api,
    make_webhook_request,
)


async def make_order(client, headers):
    quotes = await create_quote_via_api(client, headers)
    return await create_order_via_api(client, headers, quotes[0]["quote_id"])


async def get_partner_order_id(session, order_id: str) -> str:
    row = (
        await session.execute(select(Order).where(Order.id == order_id))
    ).scalar_one()
    return row.partner_order_id


async def send_webhook(
    client, partner_order_id, event_type, partner_code="mock_fiat_alpha", **kwargs
):
    req = make_webhook_request(partner_order_id, event_type, **kwargs)
    return await client.post(
        f"/api/v1/webhooks/partners/{partner_code}",
        content=req["content"],
        headers=req["headers"],
    )


async def test_webhook_advances_order(client, session):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    poid = await get_partner_order_id(session, order["id"])
    resp = await send_webhook(client, poid, "payment_detected")
    assert resp.status_code == 200
    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert detail["status"] == "PAYMENT_DETECTED"


async def test_webhook_completed_jumps_happy_path(client, session):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    poid = await get_partner_order_id(session, order["id"])
    resp = await send_webhook(client, poid, "completed")
    assert resp.status_code == 200
    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert detail["status"] == "COMPLETED"
    statuses = [e["status"] for e in detail["events"]]
    assert "PAYMENT_DETECTED" in statuses and "PAYOUT_SENT" in statuses


async def test_invalid_signature_rejected(client, session):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    poid = await get_partner_order_id(session, order["id"])
    req = make_webhook_request(poid, "payment_detected", secret="wrong-secret-value-000")
    resp = await client.post(
        "/api/v1/webhooks/partners/mock_fiat_alpha",
        content=req["content"],
        headers=req["headers"],
    )
    assert resp.status_code == 400
    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert detail["status"] == "AWAITING_PAYMENT"


async def test_stale_timestamp_rejected_replay_protection(client, session):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    poid = await get_partner_order_id(session, order["id"])
    req = make_webhook_request(
        poid, "payment_detected", timestamp=int(time.time()) - 3600
    )
    resp = await client.post(
        "/api/v1/webhooks/partners/mock_fiat_alpha",
        content=req["content"],
        headers=req["headers"],
    )
    assert resp.status_code == 400
    assert "replay" in resp.json()["message"].lower() or "tolerance" in resp.json()["message"]


async def test_duplicate_webhook_is_deduplicated(client, session):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    poid = await get_partner_order_id(session, order["id"])
    req = make_webhook_request(poid, "completed", event_id="evt-dup-1")
    for _ in range(3):
        resp = await client.post(
            "/api/v1/webhooks/partners/mock_fiat_alpha",
            content=req["content"],
            headers=req["headers"],
        )
        assert resp.status_code == 200
    events = (
        (
            await session.execute(
                select(WebhookEvent).where(WebhookEvent.external_event_id == "evt-dup-1")
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    # ledger must have exactly one gross fee posting
    postings = (
        (
            await session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.posting_key == f"order:{order['id']}:gross_service_fee"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(postings) == 1


async def test_completed_order_duplicate_webhook_noop(client, session):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    poid = await get_partner_order_id(session, order["id"])
    await send_webhook(client, poid, "completed", event_id="evt-c1")
    # a different event with the same terminal status
    resp = await send_webhook(client, poid, "completed", event_id="evt-c2")
    assert resp.status_code == 200
    all_ledger = (
        (
            await session.execute(
                select(LedgerEntry).where(LedgerEntry.order_id == order["id"])
            )
        )
        .scalars()
        .all()
    )
    gross = [e for e in all_ledger if e.posting_key.endswith("gross_service_fee")]
    assert len(gross) == 1


async def test_unknown_partner_rejected(client):
    req = make_webhook_request("whatever", "completed")
    resp = await client.post(
        "/api/v1/webhooks/partners/unknown_partner",
        content=req["content"],
        headers=req["headers"],
    )
    assert resp.status_code == 400


async def test_malformed_payload_rejected(client):
    import json

    from app.partners.mock_fiat import sign_mock_webhook

    body = b"not json"
    ts = str(int(time.time()))
    resp = await client.post(
        "/api/v1/webhooks/partners/mock_fiat_alpha",
        content=body,
        headers={
            "X-Signature": sign_mock_webhook(body, ts),
            "X-Timestamp": ts,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 400
    _ = json  # keep import for parity
