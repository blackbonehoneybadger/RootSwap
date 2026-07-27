from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OrderDirection, OrderStatus, QuoteSourceType
from app.db.base import Base, new_id, utcnow

AMOUNT = Numeric(30, 12)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency"),
        UniqueConstraint("quote_id", name="uq_orders_quote"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    quote_id: Mapped[str] = mapped_column(String(36), ForeignKey("quotes.id"), index=True)
    partner_code: Mapped[str] = mapped_column(String(64), index=True)
    partner_order_id: Mapped[str | None] = mapped_column(String(128), index=True)
    direction: Mapped[OrderDirection] = mapped_column(SAEnum(OrderDirection, native_enum=False, length=8))
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, native_enum=False, length=32), default=OrderStatus.CREATED, index=True
    )
    from_asset: Mapped[str] = mapped_column(String(16))
    from_network: Mapped[str | None] = mapped_column(String(16))
    to_asset: Mapped[str] = mapped_column(String(16))
    to_network: Mapped[str | None] = mapped_column(String(16))
    amount_in: Mapped[Decimal] = mapped_column(AMOUNT)
    amount_out: Mapped[Decimal] = mapped_column(AMOUNT)
    exchange_rate: Mapped[Decimal] = mapped_column(AMOUNT)
    service_fee: Mapped[Decimal] = mapped_column(AMOUNT, default=Decimal("0"))
    partner_fee: Mapped[Decimal] = mapped_column(AMOUNT, default=Decimal("0"))
    network_fee: Mapped[Decimal] = mapped_column(AMOUNT, default=Decimal("0"))
    total_fee: Mapped[Decimal] = mapped_column(AMOUNT, default=Decimal("0"))
    quote_source_type: Mapped[QuoteSourceType] = mapped_column(
        SAEnum(QuoteSourceType, native_enum=False, length=8)
    )
    idempotency_key: Mapped[str] = mapped_column(String(64))
    idempotency_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wallet_address_encrypted: Mapped[str | None] = mapped_column(String(1024))
    wallet_address_masked: Mapped[str | None] = mapped_column(String(64))
    payout_details_encrypted: Mapped[str | None] = mapped_column(String(2048))
    payout_details_masked: Mapped[str | None] = mapped_column(String(128))
    payment_instructions_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
