from datetime import timedelta

from sqlalchemy import select

from app.db.base import utcnow
from app.models.ledger import LedgerEntry
from app.models.order import Order
from app.models.payment_instructions import PaymentInstructions
from app.services.order_orchestrator import expire_stale_awaiting_orders
from app.services.polling import poll_active_orders_once
from tests.conftest import authed_user, create_order_via_api, create_quote_via_api


async def make_order(client, headers):
    quotes = await create_quote_via_api(client, headers)
    return await create_order_via_api(client, headers, quotes[0]["quote_id"])


async def test_polling_advances_order_without_webhook(client, session, partners):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    row = (
        await session.execute(select(Order).where(Order.id == order["id"]))
    ).scalar_one()
    # partner progressed but webhook never arrived
    partners["alpha"].set_order_status(row.partner_order_id, "processing")
    changed = await poll_active_orders_once(session)
    assert changed == 1
    await session.refresh(row)
    assert row.status.value == "PROCESSING"


async def test_polling_completes_and_posts_ledger_once(client, session, partners):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    row = (
        await session.execute(select(Order).where(Order.id == order["id"]))
    ).scalar_one()
    partners["alpha"].set_order_status(row.partner_order_id, "completed")
    await poll_active_orders_once(session)
    await session.refresh(row)
    assert row.status.value == "COMPLETED"
    # second pass: final status -> not polled, no duplicate ledger
    changed = await poll_active_orders_once(session)
    assert changed == 0
    gross = (
        (
            await session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.posting_key == f"order:{row.id}:gross_service_fee"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(gross) == 1


async def test_polling_skips_final_statuses(client, session, partners):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    row = (
        await session.execute(select(Order).where(Order.id == order["id"]))
    ).scalar_one()
    partners["alpha"].set_order_status(row.partner_order_id, "expired")
    await poll_active_orders_once(session)
    await session.refresh(row)
    assert row.status.value == "EXPIRED"
    # partner "resurrects" the order; we must not touch it anymore
    partners["alpha"].set_order_status(row.partner_order_id, "completed")
    changed = await poll_active_orders_once(session)
    assert changed == 0
    await session.refresh(row)
    assert row.status.value == "EXPIRED"


async def test_expired_payment_instructions_expire_order(client, session):
    headers, _ = await authed_user(client)
    order = await make_order(client, headers)
    row = (
        await session.execute(select(Order).where(Order.id == order["id"]))
    ).scalar_one()
    instructions = (
        await session.execute(
            select(PaymentInstructions).where(
                PaymentInstructions.id == row.payment_instructions_id
            )
        )
    ).scalar_one()
    instructions.expires_at = utcnow() - timedelta(seconds=1)
    await session.commit()
    expired = await expire_stale_awaiting_orders(session)
    assert expired == 1
    await session.refresh(row)
    assert row.status.value == "EXPIRED"
    assert instructions.deleted_at is not None
    # expired instructions are no longer returned by the API
    detail = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert detail["payment_instructions"] is None
