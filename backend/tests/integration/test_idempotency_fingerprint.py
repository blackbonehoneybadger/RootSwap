"""Same Idempotency-Key with different payload → 409."""

import uuid

from tests.conftest import authed_user, create_order_via_api, create_quote_via_api


async def test_idempotency_payload_conflict(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    key = uuid.uuid4().hex
    order1 = await create_order_via_api(
        client, headers, quotes[0]["quote_id"], idempotency_key=key
    )
    # Second quote for a different payload under the same key
    quotes2 = await create_quote_via_api(client, headers)
    resp = await client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "quote_id": quotes2[0]["quote_id"],
            "idempotency_key": key,
            "wallet_address": "4" + "B" * 94,
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "idempotency_conflict"
    # original order still fetchable
    detail = await client.get(f"/api/v1/orders/{order1['id']}", headers=headers)
    assert detail.status_code == 200
