"""Shared side effects when an order reaches key terminal / milestone statuses."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderStatus
from app.models.order import Order
from app.services import referral as referral_service
from app.services.ledger import post_completed_order, post_refund
from app.services.notifications import notify_order_status


async def apply_status_side_effects(
    session: AsyncSession,
    order: Order,
    previous_status: OrderStatus,
) -> None:
    """Ledger, referral, refund bookkeeping — idempotent via posting keys."""
    if order.status == OrderStatus.COMPLETED and previous_status != OrderStatus.COMPLETED:
        reward = await referral_service.accrue_reward_for_completed_order(session, order)
        reward_amount = reward.reward_amount if reward else 0
        await post_completed_order(session, order, reward_amount)

    if order.status == OrderStatus.REFUNDED:
        await post_refund(session, order)
        await referral_service.cancel_rewards_for_order(session, order.id)

    await notify_order_status(session, order)
