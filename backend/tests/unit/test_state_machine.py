from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.enums import ActorType, OrderDirection, OrderStatus, QuoteSourceType
from app.core.errors import InvalidTransitionError
from app.db.base import utcnow
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.models.quote import Quote
from app.services.state_machine import (
    advance_along_happy_path,
    is_transition_allowed,
    transition,
)
from tests.conftest import create_user


async def make_order(session, user, status=OrderStatus.CREATED) -> Order:
    quote = Quote(
        user_id=user.id,
        partner_code="mock_fiat_alpha",
        direction=OrderDirection.BUY,
        from_asset="RUB",
        to_asset="XMR",
        to_network="XMR",
        amount_in=Decimal("50000"),
        amount_out=Decimal("2.4"),
        exchange_rate=Decimal("20000"),
        service_fee=Decimal("450"),
        quote_source_type=QuoteSourceType.MOCK,
        expires_at=utcnow() + timedelta(minutes=2),
    )
    session.add(quote)
    await session.flush()
    order = Order(
        user_id=user.id,
        quote_id=quote.id,
        partner_code="mock_fiat_alpha",
        direction=OrderDirection.BUY,
        status=status,
        from_asset="RUB",
        to_asset="XMR",
        to_network="XMR",
        amount_in=Decimal("50000"),
        amount_out=Decimal("2.4"),
        exchange_rate=Decimal("20000"),
        service_fee=Decimal("450"),
        quote_source_type=QuoteSourceType.MOCK,
        idempotency_key=f"idem-{status.value}",
    )
    session.add(order)
    await session.commit()
    return order


async def test_happy_path_buy(session):
    user = await create_user(session, 1)
    order = await make_order(session, user)
    chain = [
        OrderStatus.QUOTE_CONFIRMED,
        OrderStatus.AWAITING_PAYMENT,
        OrderStatus.PAYMENT_DETECTED,
        OrderStatus.PAYMENT_CONFIRMING,
        OrderStatus.PROCESSING,
        OrderStatus.PAYOUT_SENT,
        OrderStatus.COMPLETED,
    ]
    actors = [
        ActorType.USER, ActorType.SYSTEM, ActorType.PARTNER, ActorType.PARTNER,
        ActorType.PARTNER, ActorType.PARTNER, ActorType.PARTNER,
    ]
    for target, actor in zip(chain, actors, strict=False):
        order = await transition(session, order, target, actor)
    await session.commit()
    assert order.status == OrderStatus.COMPLETED
    assert order.completed_at is not None
    assert order.version == len(chain)


async def test_forbidden_transition_raises_and_audits(session):
    user = await create_user(session, 2)
    order = await make_order(session, user)
    with pytest.raises(InvalidTransitionError):
        await transition(session, order, OrderStatus.COMPLETED, ActorType.USER)
    # order untouched
    await session.refresh(order)
    assert order.status == OrderStatus.CREATED
    assert order.version == 0
    audits = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_id == order.id)))
        .scalars().all()
    )
    assert any(a.action == "order.transition.denied" for a in audits)


async def test_user_cannot_mark_payment_detected(session):
    assert not is_transition_allowed(
        OrderStatus.AWAITING_PAYMENT, OrderStatus.PAYMENT_DETECTED, ActorType.USER
    )


async def test_version_mismatch_rejected(session):
    user = await create_user(session, 3)
    order = await make_order(session, user)
    with pytest.raises(InvalidTransitionError):
        await transition(
            session, order, OrderStatus.QUOTE_CONFIRMED, ActorType.USER,
            expected_version=99,
        )


async def test_same_status_is_noop(session):
    user = await create_user(session, 4)
    order = await make_order(session, user)
    result = await transition(session, order, OrderStatus.CREATED, ActorType.USER)
    assert result.version == 0


async def test_events_written_for_each_transition(session):
    user = await create_user(session, 5)
    order = await make_order(session, user)
    await transition(session, order, OrderStatus.QUOTE_CONFIRMED, ActorType.USER)
    await session.commit()
    events = (
        (await session.execute(select(OrderEvent).where(OrderEvent.order_id == order.id)))
        .scalars().all()
    )
    assert len(events) == 1
    assert events[0].status == OrderStatus.QUOTE_CONFIRMED


async def test_advance_along_happy_path_walks_intermediate_steps(session):
    user = await create_user(session, 6)
    order = await make_order(session, user, status=OrderStatus.AWAITING_PAYMENT)
    order = await advance_along_happy_path(
        session, order, OrderStatus.COMPLETED, ActorType.PARTNER
    )
    await session.commit()
    assert order.status == OrderStatus.COMPLETED
    events = (
        (await session.execute(select(OrderEvent).where(OrderEvent.order_id == order.id)))
        .scalars().all()
    )
    statuses = {e.status for e in events}
    assert OrderStatus.PAYMENT_DETECTED in statuses
    assert OrderStatus.PROCESSING in statuses


async def test_advance_backwards_rejected(session):
    user = await create_user(session, 7)
    order = await make_order(session, user, status=OrderStatus.PROCESSING)
    with pytest.raises(InvalidTransitionError):
        await advance_along_happy_path(
            session, order, OrderStatus.PAYMENT_DETECTED, ActorType.PARTNER
        )


async def test_refund_chain(session):
    user = await create_user(session, 8)
    order = await make_order(session, user, status=OrderStatus.COMPLETED)
    order = await transition(session, order, OrderStatus.REFUND_REQUESTED, ActorType.USER)
    order = await transition(session, order, OrderStatus.REFUND_PROCESSING, ActorType.ADMIN)
    order = await transition(session, order, OrderStatus.REFUNDED, ActorType.ADMIN)
    assert order.status == OrderStatus.REFUNDED


async def test_refund_failed_recoverable(session):
    user = await create_user(session, 9)
    order = await make_order(session, user, status=OrderStatus.REFUND_PROCESSING)
    order = await transition(session, order, OrderStatus.REFUND_FAILED, ActorType.PARTNER)
    order = await transition(session, order, OrderStatus.REFUND_PROCESSING, ActorType.ADMIN)
    assert order.status == OrderStatus.REFUND_PROCESSING
