"""Single-tier referral system.

- referral_code is generated at registration
- referred_by is set exactly once, self-referral forbidden
- reward accrues only when an order reaches COMPLETED (exactly once per order)
- FROZEN while the order is disputed, CANCELLED on refund
"""

import logging
import secrets
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import OrderStatus, ReferralRewardStatus
from app.db.base import utcnow
from app.models.order import Order
from app.models.referral import ReferralRelationship, ReferralReward
from app.models.user import User

logger = logging.getLogger(__name__)

CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def generate_referral_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


async def attach_referrer(
    session: AsyncSession, user: User, referral_code: str | None
) -> bool:
    """Attach a referrer once. Returns True when relationship was created."""
    if not referral_code or user.referred_by_user_id is not None:
        return False
    referrer = (
        await session.execute(select(User).where(User.referral_code == referral_code))
    ).scalar_one_or_none()
    if referrer is None or referrer.id == user.id:
        return False
    user.referred_by_user_id = referrer.id
    session.add(
        ReferralRelationship(referrer_user_id=referrer.id, referred_user_id=user.id)
    )
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return False
    return True


def compute_reward_amount(order: Order) -> Decimal:
    settings = get_settings()
    rate = Decimal(settings.referral_reward_percent) / Decimal("100")
    if settings.referral_reward_basis == "net_margin":
        basis = Decimal(order.service_fee)  # net margin == service fee in mock model
    else:
        basis = Decimal(order.service_fee)
    return (basis * rate).quantize(Decimal("0.01"))


async def accrue_reward_for_completed_order(
    session: AsyncSession, order: Order
) -> ReferralReward | None:
    """Idempotent: at most one reward per order (uq_referral_reward_order_once)."""
    if order.status != OrderStatus.COMPLETED:
        return None
    user = (
        await session.execute(select(User).where(User.id == order.user_id))
    ).scalar_one()
    if user.referred_by_user_id is None:
        return None
    existing = (
        await session.execute(
            select(ReferralReward).where(ReferralReward.order_id == order.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None
    settings = get_settings()
    amount = compute_reward_amount(order)
    if amount <= 0:
        return None
    reward = ReferralReward(
        order_id=order.id,
        referrer_user_id=user.referred_by_user_id,
        referred_user_id=user.id,
        reward_currency="RUB",
        reward_amount=amount,
        reward_rate=Decimal(settings.referral_reward_percent) / Decimal("100"),
        status=ReferralRewardStatus.CONFIRMED,
        posting_key=f"referral:{order.id}",
    )
    session.add(reward)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return None
    return reward


async def freeze_rewards_for_order(session: AsyncSession, order_id: str) -> None:
    reward = (
        await session.execute(
            select(ReferralReward).where(ReferralReward.order_id == order_id)
        )
    ).scalar_one_or_none()
    if reward and reward.status in (
        ReferralRewardStatus.PENDING,
        ReferralRewardStatus.CONFIRMED,
    ):
        reward.status = ReferralRewardStatus.FROZEN
        await session.flush()


async def cancel_rewards_for_order(session: AsyncSession, order_id: str) -> None:
    reward = (
        await session.execute(
            select(ReferralReward).where(ReferralReward.order_id == order_id)
        )
    ).scalar_one_or_none()
    if reward and reward.status != ReferralRewardStatus.PAID:
        reward.status = ReferralRewardStatus.CANCELLED
        await session.flush()


async def get_stats(session: AsyncSession, user: User, bot_username: str = "RootSwapBot") -> dict:
    referred_count = (
        await session.execute(
            select(func.count()).select_from(ReferralRelationship).where(
                ReferralRelationship.referrer_user_id == user.id
            )
        )
    ).scalar_one()
    active_count = (
        await session.execute(
            select(func.count(func.distinct(Order.user_id)))
            .select_from(Order)
            .join(
                ReferralRelationship,
                ReferralRelationship.referred_user_id == Order.user_id,
            )
            .where(
                ReferralRelationship.referrer_user_id == user.id,
                Order.status == OrderStatus.COMPLETED,
            )
        )
    ).scalar_one()
    rewards = (
        (
            await session.execute(
                select(ReferralReward)
                .where(ReferralReward.referrer_user_id == user.id)
                .order_by(ReferralReward.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    totals: dict[str, Decimal] = {}
    for reward in rewards:
        if reward.status in (ReferralRewardStatus.CONFIRMED, ReferralRewardStatus.PAID):
            totals[reward.reward_currency] = totals.get(
                reward.reward_currency, Decimal("0")
            ) + Decimal(reward.reward_amount)
    return {
        "referral_code": user.referral_code,
        "referral_link": f"https://t.me/{bot_username}?start=ref_{user.referral_code}",
        "referred_count": int(referred_count),
        "active_referred_count": int(active_count),
        "total_rewards": [
            {"currency": currency, "amount": str(amount)} for currency, amount in totals.items()
        ],
        "rewards": [
            {
                "order_id": r.order_id,
                "reward_amount": str(r.reward_amount),
                "reward_currency": r.reward_currency,
                "status": r.status.value,
                "created_at": r.created_at.isoformat(),
            }
            for r in rewards
        ],
    }


_ = utcnow  # imported for future paid_at handling
