from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import WebhookProcessingStatus
from app.db.base import Base, new_id, utcnow


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("partner_code", "external_event_id", name="uq_webhook_partner_event"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    partner_code: Mapped[str] = mapped_column(String(64), index=True)
    external_event_id: Mapped[str] = mapped_column(String(128), index=True)
    partner_order_id: Mapped[str | None] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0)
    processing_status: Mapped[WebhookProcessingStatus] = mapped_column(
        SAEnum(WebhookProcessingStatus, native_enum=False, length=16),
        default=WebhookProcessingStatus.RECEIVED,
    )
    processing_error: Mapped[str | None] = mapped_column(String(512))
