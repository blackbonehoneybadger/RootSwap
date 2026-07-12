from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ActorType, OrderStatus
from app.db.base import Base, new_id, utcnow


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus, native_enum=False, length=32))
    message: Mapped[str | None] = mapped_column(String(512))
    actor_type: Mapped[ActorType] = mapped_column(SAEnum(ActorType, native_enum=False, length=16))
    actor_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
