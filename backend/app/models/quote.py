from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OrderDirection, QuoteSourceType
from app.db.base import Base, new_id, utcnow

AMOUNT = Numeric(30, 12)


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    partner_code: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[OrderDirection] = mapped_column(SAEnum(OrderDirection, native_enum=False, length=8))
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
    root_score: Mapped[Decimal] = mapped_column(AMOUNT, default=Decimal("0"))
    quote_source_type: Mapped[QuoteSourceType] = mapped_column(
        SAEnum(QuoteSourceType, native_enum=False, length=8)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_partner_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
