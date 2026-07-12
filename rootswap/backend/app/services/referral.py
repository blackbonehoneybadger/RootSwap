
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import OrderStatus, ReferralRewardStatus
from app.core.exceptions import ValidationError
from app.models import Order, ReferralRelationship, ReferralReward, User
from app.services.ledger import LedgerService


class ReferralService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ledger = LedgerService()

    async def attach_referrer(
        self, session: AsyncSession, user: User, referral_code: str | None
    ) -> None:
        if not referral_code or user.referred_by_user_id:
            return
        result = await session.execute(select(User).where(User.referral_code == referral_code))
        referrer = result.scalar_one_or_none()
        if not referrer:
            return
        if referrer.id == user.id:
            raise ValidationError("Self-referral is not allowed")
        user.referred_by_user_id = referrer.id
        session.add(
            ReferralRelationship(referrer_user_id=referrer.id, referred_user_id=user.id)
        )

    async def process_completed_order(self, session: AsyncSession, order: Order) -> None:
        if order.status != OrderStatus.COMPLETED:
            return
        result = await session.execute(select(User).where(User.id == order.user_id))
        user = result.scalar_one()
        if not user.referred_by_user_id:
            return

        posting_key = f"referral:order:{order.id}"
        existing = await session.execute(
            select(ReferralReward).where(ReferralReward.posting_key == posting_key)
        )
        if existing.scalar_one_or_none():
            return

        if self.settings.referral_reward_basis == "service_fee":
            base = float(order.service_fee)
        else:
            base = float(order.service_fee) - float(order.partner_fee) - float(order.network_fee)

        reward_amount = round(base * self.settings.referral_reward_rate, 8)
        reward = ReferralReward(
            order_id=order.id,
            referrer_user_id=user.referred_by_user_id,
            referred_user_id=user.id,
            reward_currency="RUB",
            reward_amount=reward_amount,
            reward_rate=self.settings.referral_reward_rate,
            status=ReferralRewardStatus.PAID,
            posting_key=posting_key,
        )
        session.add(reward)
        await self.ledger.post_referral_liability(
            session, order.id, f"{posting_key}:liability", reward_amount
        )
        await self.ledger.post_referral_paid(
            session, order.id, f"{posting_key}:paid", reward_amount
        )

    async def freeze_on_dispute(self, session: AsyncSession, order: Order) -> None:
        result = await session.execute(
            select(ReferralReward).where(ReferralReward.order_id == order.id)
        )
        reward = result.scalar_one_or_none()
        if reward and reward.status == ReferralRewardStatus.PENDING:
            reward.status = ReferralRewardStatus.FROZEN

    async def get_stats(self, session: AsyncSession, user: User) -> dict:
        referred_count = await session.scalar(
            select(func.count()).select_from(ReferralRelationship).where(
                ReferralRelationship.referrer_user_id == user.id
            )
        )
        rewards = await session.execute(
            select(ReferralReward).where(ReferralReward.referrer_user_id == user.id)
        )
        reward_list = list(rewards.scalars().all())
        total_rewards = sum(float(r.reward_amount) for r in reward_list if r.status == ReferralRewardStatus.PAID)
        return {
            "referral_code": user.referral_code,
            "referral_link": f"https://t.me/RootSwapBot?start=ref_{user.referral_code}",
            "referred_count": referred_count or 0,
            "active_referred_users": referred_count or 0,
            "total_rewards": total_rewards,
            "rewards": [
                {
                    "order_id": str(r.order_id),
                    "amount": float(r.reward_amount),
                    "status": r.status.value,
                }
                for r in reward_list
            ],
        }
