from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DisputeStatus
from app.db.base import Base, new_id, utcnow


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    status: Mapped[DisputeStatus] = mapped_column(
        SAEnum(DisputeStatus, native_enum=False, length=16), default=DisputeStatus.OPEN
    )
    reason: Mapped[str] = mapped_column(String(512))
    evidence_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(String(1024))
    partner_reference: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
