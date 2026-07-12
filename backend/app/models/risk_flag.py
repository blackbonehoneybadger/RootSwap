from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import RiskFlagStatus
from app.db.base import Base, new_id, utcnow


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("orders.id"), index=True)
    flag_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="LOW")
    message: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[RiskFlagStatus] = mapped_column(
        SAEnum(RiskFlagStatus, native_enum=False, length=16), default=RiskFlagStatus.OPEN
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
