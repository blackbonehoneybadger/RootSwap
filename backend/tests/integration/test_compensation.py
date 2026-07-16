"""Saga compensation: an orphaned remote partner order must be cancelled when
local persistence fails after the remote order was created."""

import uuid

from sqlalchemy import func, select

from app.models.order import Order
from app.models.payment_instructions import PaymentInstructions
from app.models.quote import Quote
from tests.conftest import VALID_XMR, authed_user, create_quote_via_api


async def test_partner_order_compensated_on_local_failure(
    client, session, partners, monkeypatch
):
    headers, _ = await authed_user(client, telegram_id=2001)
    quotes = await create_quote_via_api(client, headers, to_asset="XMR", to_network="XMR")
    alpha_q = next(q for q in quotes if q["partner_code"] == "mock_fiat_alpha")

    # Force a local persistence failure AFTER the remote order is created.
    import app.services.order_orchestrator as orch

    def boom(*_a, **_k):
        raise RuntimeError("simulated local persistence failure")

    monkeypatch.setattr(orch, "_build_payment_instructions", boom)

    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": alpha_q["quote_id"],
            "idempotency_key": uuid.uuid4().hex,
            "wallet_address": VALID_XMR,
        },
        headers=headers,
    )
    # user gets a clear error, NOT a fake-successful order
    assert resp.status_code == 502, resp.text

    # the remote order was cancelled by compensation (mock marks it "cancelled")
    alpha = partners["alpha"]
    assert any(
        o["status"] == "cancelled" for o in alpha._orders.values()
    ), "cancel_order must have been called during compensation"

    # no local order and no payment instructions persisted
    n_orders = (
        await session.execute(select(func.count()).select_from(Order))
    ).scalar_one()
    assert n_orders == 0, "no local order may survive a compensated failure"
    n_pi = (
        await session.execute(select(func.count()).select_from(PaymentInstructions))
    ).scalar_one()
    assert n_pi == 0

    # the quote must NOT be left permanently consumed without an order
    quote = (
        await session.execute(select(Quote).where(Quote.id == alpha_q["quote_id"]))
    ).scalar_one()
    assert quote.consumed_at is None, "quote must be released when the order is compensated"


async def test_compensation_records_audit_when_cancel_also_fails(
    client, session, partners, monkeypatch
):
    headers, _ = await authed_user(client, telegram_id=2002)
    quotes = await create_quote_via_api(client, headers, to_asset="XMR", to_network="XMR")
    alpha_q = next(q for q in quotes if q["partner_code"] == "mock_fiat_alpha")

    import app.services.order_orchestrator as orch
    from app.partners.base import PartnerError

    def boom(*_a, **_k):
        raise RuntimeError("local failure")

    async def failing_cancel(*_a, **_k):
        raise PartnerError("partner cancel unavailable")

    monkeypatch.setattr(orch, "_build_payment_instructions", boom)
    monkeypatch.setattr(partners["alpha"], "cancel_order", failing_cancel)

    resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": alpha_q["quote_id"],
            "idempotency_key": uuid.uuid4().hex,
            "wallet_address": VALID_XMR,
        },
        headers=headers,
    )
    assert resp.status_code == 502

    # a recovery AuditLog must exist flagging the orphaned remote order
    from app.models.audit_log import AuditLog

    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "order.partner_compensation.cancel_failed"
                )
            )
        )
        .scalars()
        .all()
    )
    assert audits, "a recovery audit record must be written when cancel also fails"
    assert audits[0].metadata_ and audits[0].metadata_.get("needs_recovery") is True
