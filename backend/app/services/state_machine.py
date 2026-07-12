"""Single order state transition service.

Every status change in the system MUST go through `transition()`. Forbidden
transitions raise InvalidTransitionError, write an AuditLog entry and leave the
order untouched. Optimistic locking is enforced via the `version` column.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FINAL_ORDER_STATUSES, ActorType, OrderStatus
from app.core.errors import InvalidTransitionError
from app.db.base import utcnow
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.observability.metrics import metrics
from app.services.audit import write_audit

logger = logging.getLogger(__name__)

S = OrderStatus
A = ActorType

# (from, to) -> set of actor types allowed to perform the transition
TRANSITIONS: dict[tuple[OrderStatus, OrderStatus], set[ActorType]] = {
    (S.CREATED, S.QUOTE_CONFIRMED): {A.USER, A.SYSTEM},
    (S.QUOTE_CONFIRMED, S.AWAITING_PAYMENT): {A.SYSTEM, A.PARTNER},
    (S.AWAITING_PAYMENT, S.PAYMENT_DETECTED): {A.PARTNER, A.SYSTEM, A.ADMIN},
    (S.PAYMENT_DETECTED, S.PAYMENT_CONFIRMING): {A.PARTNER, A.SYSTEM, A.ADMIN},
    (S.PAYMENT_CONFIRMING, S.PROCESSING): {A.PARTNER, A.SYSTEM, A.ADMIN},
    (S.PROCESSING, S.PAYOUT_SENT): {A.PARTNER, A.SYSTEM, A.ADMIN},
    (S.PAYOUT_SENT, S.COMPLETED): {A.PARTNER, A.SYSTEM, A.ADMIN},
    # error / operational flows
    (S.AWAITING_PAYMENT, S.EXPIRED): {A.SYSTEM, A.PARTNER, A.ADMIN},
    (S.AWAITING_PAYMENT, S.CANCELLED): {A.USER, A.ADMIN, A.SYSTEM},
    (S.CREATED, S.CANCELLED): {A.USER, A.ADMIN, A.SYSTEM},
    (S.QUOTE_CONFIRMED, S.CANCELLED): {A.USER, A.ADMIN, A.SYSTEM},
    (S.PAYMENT_DETECTED, S.DISPUTED): {A.USER, A.ADMIN},
    (S.PAYMENT_CONFIRMING, S.DISPUTED): {A.USER, A.ADMIN},
    (S.PROCESSING, S.DISPUTED): {A.USER, A.ADMIN},
    (S.PAYOUT_SENT, S.DISPUTED): {A.USER, A.ADMIN},
    (S.COMPLETED, S.DISPUTED): {A.USER, A.ADMIN},
    (S.PROCESSING, S.FAILED): {A.PARTNER, A.SYSTEM, A.ADMIN},
    (S.PAYMENT_CONFIRMING, S.FAILED): {A.PARTNER, A.SYSTEM, A.ADMIN},
    (S.PAYOUT_SENT, S.FAILED): {A.PARTNER, A.SYSTEM, A.ADMIN},
    (S.DISPUTED, S.PROCESSING): {A.ADMIN},
    (S.DISPUTED, S.COMPLETED): {A.ADMIN},
    (S.DISPUTED, S.REFUND_REQUESTED): {A.ADMIN, A.USER},
    (S.COMPLETED, S.REFUND_REQUESTED): {A.USER, A.ADMIN},
    (S.REFUND_REQUESTED, S.REFUND_PROCESSING): {A.ADMIN, A.PARTNER, A.SYSTEM},
    (S.REFUND_PROCESSING, S.REFUNDED): {A.PARTNER, A.ADMIN, A.SYSTEM},
    (S.REFUND_PROCESSING, S.REFUND_FAILED): {A.PARTNER, A.ADMIN, A.SYSTEM},
    (S.REFUND_FAILED, S.REFUND_PROCESSING): {A.ADMIN},
    (S.FAILED, S.REFUND_REQUESTED): {A.ADMIN, A.USER},
}

# canonical happy path used to walk multi-step webhook updates
HAPPY_PATH = [
    S.CREATED,
    S.QUOTE_CONFIRMED,
    S.AWAITING_PAYMENT,
    S.PAYMENT_DETECTED,
    S.PAYMENT_CONFIRMING,
    S.PROCESSING,
    S.PAYOUT_SENT,
    S.COMPLETED,
]


def is_transition_allowed(
    current: OrderStatus, target: OrderStatus, actor: ActorType
) -> bool:
    allowed = TRANSITIONS.get((current, target))
    return allowed is not None and actor in allowed


async def transition(
    session: AsyncSession,
    order: Order,
    target: OrderStatus,
    actor_type: ActorType,
    actor_id: str | None = None,
    source: str = "api",
    message: str | None = None,
    metadata: dict | None = None,
    expected_version: int | None = None,
) -> Order:
    current = order.status

    if expected_version is not None and order.version != expected_version:
        raise InvalidTransitionError(
            "order version mismatch (concurrent update)",
            current_version=order.version,
            expected_version=expected_version,
        )

    if current == target:
        return order  # idempotent no-op

    if not is_transition_allowed(current, target, actor_type):
        write_audit(
            session,
            action="order.transition.denied",
            actor_user_id=actor_id,
            actor_role=actor_type.value,
            entity_type="order",
            entity_id=order.id,
            reason=f"{current.value} -> {target.value} by {actor_type.value} via {source}",
            metadata=metadata,
        )
        await session.commit()
        metrics.inc("order_transition_denied_total", from_status=current.value, to_status=target.value)
        raise InvalidTransitionError(
            f"transition {current.value} -> {target.value} is not allowed for {actor_type.value}",
            current=current.value,
            target=target.value,
            actor=actor_type.value,
        )

    order.status = target
    order.version += 1
    now = utcnow()
    order.updated_at = now
    if target == S.COMPLETED:
        order.completed_at = now
    if target == S.EXPIRED:
        order.expired_at = now

    session.add(
        OrderEvent(
            order_id=order.id,
            status=target,
            message=message or f"{current.value} -> {target.value}",
            actor_type=actor_type,
            actor_id=actor_id,
            payload=metadata,
        )
    )
    metrics.inc("order_transition_total", from_status=current.value, to_status=target.value)
    await session.flush()
    return order


async def advance_along_happy_path(
    session: AsyncSession,
    order: Order,
    target: OrderStatus,
    actor_type: ActorType,
    actor_id: str | None = None,
    source: str = "webhook",
    message: str | None = None,
) -> Order:
    """Walk intermediate happy-path statuses when a partner update skips steps."""
    if order.status == target:
        return order
    if target not in HAPPY_PATH or order.status not in HAPPY_PATH:
        return await transition(
            session, order, target, actor_type, actor_id, source, message
        )
    current_idx = HAPPY_PATH.index(order.status)
    target_idx = HAPPY_PATH.index(target)
    if target_idx <= current_idx:
        raise InvalidTransitionError(
            f"cannot move backwards {order.status.value} -> {target.value}"
        )
    for status in HAPPY_PATH[current_idx + 1 : target_idx + 1]:
        order = await transition(
            session, order, status, actor_type, actor_id, source, message
        )
    return order


def is_final(status: OrderStatus) -> bool:
    return status in FINAL_ORDER_STATUSES
