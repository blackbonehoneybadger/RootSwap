import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.enums import (
    CircuitBreakerState,
    DisputeStatus,
    LedgerEntryType,
    OrderDirection,
    OrderStatus,
    QuoteSourceType,
    ReferralRewardStatus,
    RiskFlagStatus,
    WebhookProcessingStatus,
)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    referred_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    referral_tier: Mapped[int] = mapped_column(Integer, default=1)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="user")


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    partner_code: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[OrderDirection] = mapped_column(Enum(OrderDirection, name="order_direction"))
    from_asset: Mapped[str] = mapped_column(String(32))
    from_network: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_asset: Mapped[str] = mapped_column(String(32))
    to_network: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount_in: Mapped[float] = mapped_column(Numeric(24, 8))
    amount_out: Mapped[float] = mapped_column(Numeric(24, 8))
    exchange_rate: Mapped[float] = mapped_column(Numeric(24, 8))
    service_fee: Mapped[float] = mapped_column(Numeric(24, 8))
    partner_fee: Mapped[float] = mapped_column(Numeric(24, 8))
    network_fee: Mapped[float] = mapped_column(Numeric(24, 8))
    total_fee: Mapped[float] = mapped_column(Numeric(24, 8))
    root_score: Mapped[float] = mapped_column(Float, default=0.0)
    quote_source_type: Mapped[QuoteSourceType] = mapped_column(
        Enum(QuoteSourceType, name="quote_source_type")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_partner_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="quotes")
    orders: Mapped[list["Order"]] = relationship(back_populates="quote")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_orders_idempotency_key"),)

    # idempotency_fingerprint added below — see column list

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id"), index=True)
    partner_code: Mapped[str] = mapped_column(String(64), index=True)
    partner_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    direction: Mapped[OrderDirection] = mapped_column(Enum(OrderDirection, name="order_direction", create_type=False))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.CREATED, index=True
    )
    from_asset: Mapped[str] = mapped_column(String(32))
    from_network: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_asset: Mapped[str] = mapped_column(String(32))
    to_network: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount_in: Mapped[float] = mapped_column(Numeric(24, 8))
    amount_out: Mapped[float] = mapped_column(Numeric(24, 8))
    exchange_rate: Mapped[float] = mapped_column(Numeric(24, 8))
    service_fee: Mapped[float] = mapped_column(Numeric(24, 8))
    partner_fee: Mapped[float] = mapped_column(Numeric(24, 8))
    network_fee: Mapped[float] = mapped_column(Numeric(24, 8))
    total_fee: Mapped[float] = mapped_column(Numeric(24, 8))
    quote_source_type: Mapped[QuoteSourceType] = mapped_column(
        Enum(QuoteSourceType, name="quote_source_type", create_type=False)
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    idempotency_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wallet_address_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    wallet_address_masked: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payout_details_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    payout_details_masked: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Denormalized pointer only — NO FK here.
    # Owning FK is payment_instructions.order_id → orders.id.
    # A bidirectional FK pair caused ForeignKeyViolationError on PostgreSQL
    # during flush (SQLite tests hid it because FK enforcement differs).
    payment_instructions_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="orders")
    quote: Mapped["Quote"] = relationship(back_populates="orders")
    events: Mapped[list["OrderEvent"]] = relationship(back_populates="order")
    payment_instructions: Mapped["PaymentInstructions | None"] = relationship(
        back_populates="order",
        foreign_keys="PaymentInstructions.order_id",
        uselist=False,
    )


class PaymentInstructions(Base):
    __tablename__ = "payment_instructions"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payment_instructions_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    partner_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payment_method: Mapped[str] = mapped_column(String(64))
    bank_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recipient_name_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_number_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_number_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    sbp_phone_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    masked_recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    masked_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    masked_card: Mapped[str | None] = mapped_column(String(64), nullable=True)
    masked_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deposit_address_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    deposit_address_masked: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(24, 8))
    currency: Mapped[str] = mapped_column(String(16))
    payment_comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(
        back_populates="payment_instructions", foreign_keys=[order_id]
    )


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="order_status", create_type=False))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="events")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (UniqueConstraint("posting_key", name="uq_ledger_posting_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    posting_key: Mapped[str] = mapped_column(String(255), unique=True)
    entry_type: Mapped[LedgerEntryType] = mapped_column(Enum(LedgerEntryType, name="ledger_entry_type"))
    currency: Mapped[str] = mapped_column(String(16))
    amount: Mapped[float] = mapped_column(Numeric(24, 8))
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recipient: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReferralRelationship(Base):
    __tablename__ = "referral_relationships"
    __table_args__ = (UniqueConstraint("referred_user_id", name="uq_referral_referred_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    referred_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    __table_args__ = (UniqueConstraint("posting_key", name="uq_referral_reward_posting_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    referrer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    referred_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reward_currency: Mapped[str] = mapped_column(String(16))
    reward_amount: Mapped[float] = mapped_column(Numeric(24, 8))
    reward_rate: Mapped[float] = mapped_column(Numeric(8, 4))
    status: Mapped[ReferralRewardStatus] = mapped_column(
        Enum(ReferralRewardStatus, name="referral_reward_status"), default=ReferralRewardStatus.PENDING
    )
    posting_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    adapter_type: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quote_source_type: Mapped[QuoteSourceType] = mapped_column(
        Enum(QuoteSourceType, name="quote_source_type", create_type=False)
    )
    environment: Mapped[str] = mapped_column(String(32), default="sandbox")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)
    average_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    success_rate: Mapped[float] = mapped_column(Float, default=1.0)
    circuit_breaker_state: Mapped[CircuitBreakerState] = mapped_column(
        Enum(CircuitBreakerState, name="circuit_breaker_state"), default=CircuitBreakerState.CLOSED
    )
    circuit_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("partner_code", "external_event_id", name="uq_webhook_partner_event"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_code: Mapped[str] = mapped_column(String(64), index=True)
    external_event_id: Mapped[str] = mapped_column(String(255))
    partner_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(128))
    raw_payload: Mapped[dict] = mapped_column(JSON)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0)
    processing_status: Mapped[WebhookProcessingStatus] = mapped_column(
        Enum(WebhookProcessingStatus, name="webhook_processing_status"),
        default=WebhookProcessingStatus.PENDING,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[DisputeStatus] = mapped_column(
        Enum(DisputeStatus, name="dispute_status"), default=DisputeStatus.OPEN
    )
    reason: Mapped[str] = mapped_column(Text)
    evidence_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    partner_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    flag_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[RiskFlagStatus] = mapped_column(
        Enum(RiskFlagStatus, name="risk_flag_status"), default=RiskFlagStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
