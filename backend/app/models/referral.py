from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ReferralRewardStatus
from app.db.base import Base, new_id, utcnow


class ReferralRelationship(Base):
    __tablename__ = "referral_relationships"
    __table_args__ = (
        UniqueConstraint("referred_user_id", name="uq_referral_referred_once"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    referrer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_referral_reward_order_once"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), index=True)
    referrer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    referred_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    reward_currency: Mapped[str] = mapped_column(String(16))
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    reward_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    status: Mapped[ReferralRewardStatus] = mapped_column(
        SAEnum(ReferralRewardStatus, native_enum=False, length=16),
        default=ReferralRewardStatus.PENDING,
    )
    posting_key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
