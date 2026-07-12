from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_id, utcnow


class PaymentInstructions(Base):
    __tablename__ = "payment_instructions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), index=True)
    partner_order_id: Mapped[str | None] = mapped_column(String(128))
    payment_method: Mapped[str] = mapped_column(String(32))
    bank_name: Mapped[str | None] = mapped_column(String(64))
    recipient_name_encrypted: Mapped[str | None] = mapped_column(String(1024))
    account_number_encrypted: Mapped[str | None] = mapped_column(String(1024))
    card_number_encrypted: Mapped[str | None] = mapped_column(String(1024))
    sbp_phone_encrypted: Mapped[str | None] = mapped_column(String(1024))
    masked_recipient_name: Mapped[str | None] = mapped_column(String(64))
    masked_account: Mapped[str | None] = mapped_column(String(64))
    masked_card: Mapped[str | None] = mapped_column(String(64))
    masked_phone: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    currency: Mapped[str] = mapped_column(String(16))
    payment_comment: Mapped[str | None] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
