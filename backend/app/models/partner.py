from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import CircuitBreakerState, QuoteSourceType
from app.db.base import Base, new_id, utcnow


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    adapter_type: Mapped[str] = mapped_column(String(32))  # fiat | crypto
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quote_source_type: Mapped[QuoteSourceType] = mapped_column(
        SAEnum(QuoteSourceType, native_enum=False, length=8)
    )
    environment: Mapped[str] = mapped_column(String(16), default="mock")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)
    average_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    success_rate: Mapped[float] = mapped_column(Float, default=1.0)
    circuit_breaker_state: Mapped[CircuitBreakerState] = mapped_column(
        SAEnum(CircuitBreakerState, native_enum=False, length=16),
        default=CircuitBreakerState.CLOSED,
    )
    circuit_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(String(256))
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
