"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("username", sa.String(255)),
        sa.Column("first_name", sa.String(255)),
        sa.Column("referral_code", sa.String(32), nullable=False, unique=True),
        sa.Column("referred_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("referral_tier", sa.Integer(), server_default="1"),
        sa.Column("is_blocked", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "partners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("adapter_type", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("quote_source_type", sa.Enum("MOCK", "SANDBOX", "REAL", name="quote_source_type")),
        sa.Column("environment", sa.String(32), server_default="sandbox"),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0"),
        sa.Column("total_requests", sa.Integer(), server_default="0"),
        sa.Column("successful_requests", sa.Integer(), server_default="0"),
        sa.Column("failed_requests", sa.Integer(), server_default="0"),
        sa.Column("average_latency_ms", sa.Float(), server_default="0"),
        sa.Column("success_rate", sa.Float(), server_default="1"),
        sa.Column(
            "circuit_breaker_state",
            sa.Enum("CLOSED", "OPEN", "HALF_OPEN", name="circuit_breaker_state"),
            server_default="CLOSED",
        ),
        sa.Column("circuit_opened_at", sa.DateTime(timezone=True)),
        sa.Column("cooldown_until", sa.DateTime(timezone=True)),
        sa.Column("disabled_reason", sa.Text()),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("partner_code", sa.String(64), nullable=False),
        sa.Column("direction", sa.Enum("BUY", "SELL", name="order_direction"), nullable=False),
        sa.Column("from_asset", sa.String(32), nullable=False),
        sa.Column("from_network", sa.String(32)),
        sa.Column("to_asset", sa.String(32), nullable=False),
        sa.Column("to_network", sa.String(32)),
        sa.Column("amount_in", sa.Numeric(24, 8), nullable=False),
        sa.Column("amount_out", sa.Numeric(24, 8), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(24, 8), nullable=False),
        sa.Column("service_fee", sa.Numeric(24, 8), nullable=False),
        sa.Column("partner_fee", sa.Numeric(24, 8), nullable=False),
        sa.Column("network_fee", sa.Numeric(24, 8), nullable=False),
        sa.Column("total_fee", sa.Numeric(24, 8), nullable=False),
        sa.Column("root_score", sa.Float(), server_default="0"),
        sa.Column("quote_source_type", sa.Enum("MOCK", "SANDBOX", "REAL", name="quote_source_type", create_type=False)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("raw_partner_response", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "payment_instructions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_order_id", sa.String(128)),
        sa.Column("payment_method", sa.String(64), nullable=False),
        sa.Column("bank_name", sa.String(128)),
        sa.Column("recipient_name_encrypted", sa.Text()),
        sa.Column("account_number_encrypted", sa.Text()),
        sa.Column("card_number_encrypted", sa.Text()),
        sa.Column("sbp_phone_encrypted", sa.Text()),
        sa.Column("masked_recipient_name", sa.String(255)),
        sa.Column("masked_account", sa.String(64)),
        sa.Column("masked_card", sa.String(64)),
        sa.Column("masked_phone", sa.String(64)),
        sa.Column("deposit_address_encrypted", sa.Text()),
        sa.Column("deposit_address_masked", sa.String(255)),
        sa.Column("amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("currency", sa.String(16), nullable=False),
        sa.Column("payment_comment", sa.String(255)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("partner_code", sa.String(64), nullable=False),
        sa.Column("partner_order_id", sa.String(128)),
        sa.Column("direction", sa.Enum("BUY", "SELL", name="order_direction", create_type=False)),
        sa.Column("status", sa.Enum("CREATED", "QUOTE_CONFIRMED", "AWAITING_PAYMENT", "PAYMENT_DETECTED", "PAYMENT_CONFIRMING", "PROCESSING", "PAYOUT_SENT", "COMPLETED", "EXPIRED", "FAILED", "DISPUTED", "REFUND_REQUESTED", "REFUND_PROCESSING", "REFUNDED", "REFUND_FAILED", "CANCELLED", name="order_status"), server_default="CREATED"),
        sa.Column("from_asset", sa.String(32), nullable=False),
        sa.Column("from_network", sa.String(32)),
        sa.Column("to_asset", sa.String(32), nullable=False),
        sa.Column("to_network", sa.String(32)),
        sa.Column("amount_in", sa.Numeric(24, 8), nullable=False),
        sa.Column("amount_out", sa.Numeric(24, 8), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(24, 8), nullable=False),
        sa.Column("service_fee", sa.Numeric(24, 8), nullable=False),
        sa.Column("partner_fee", sa.Numeric(24, 8), nullable=False),
        sa.Column("network_fee", sa.Numeric(24, 8), nullable=False),
        sa.Column("total_fee", sa.Numeric(24, 8), nullable=False),
        sa.Column("quote_source_type", sa.Enum("MOCK", "SANDBOX", "REAL", name="quote_source_type", create_type=False)),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("idempotency_fingerprint", sa.String(64), nullable=True),
        sa.Column("wallet_address_encrypted", sa.Text()),
        sa.Column("wallet_address_masked", sa.String(255)),
        sa.Column("payout_details_encrypted", sa.Text()),
        sa.Column("payout_details_masked", sa.String(255)),
        # Nullable pointer without FK — ownership is payment_instructions.order_id.
        # Bidirectional FKs caused circular FK violations on PostgreSQL inserts.
        sa.Column("payment_instructions_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("expired_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_foreign_key("fk_payment_instructions_order", "payment_instructions", "orders", ["order_id"], ["id"])
    op.create_unique_constraint(
        "uq_payment_instructions_order_id", "payment_instructions", ["order_id"]
    )
    op.create_table(
        "order_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("status", sa.Enum("CREATED", "QUOTE_CONFIRMED", "AWAITING_PAYMENT", "PAYMENT_DETECTED", "PAYMENT_CONFIRMING", "PROCESSING", "PAYOUT_SENT", "COMPLETED", "EXPIRED", "FAILED", "DISPUTED", "REFUND_REQUESTED", "REFUND_PROCESSING", "REFUNDED", "REFUND_FAILED", "CANCELLED", name="order_status", create_type=False)),
        sa.Column("message", sa.Text()),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(128)),
        sa.Column("payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("posting_key", sa.String(255), nullable=False, unique=True),
        sa.Column("entry_type", sa.Enum("GROSS_SERVICE_FEE", "PARTNER_REWARD", "PARTNER_COST", "NETWORK_COST", "REFERRAL_LIABILITY", "REFERRAL_PAID", "REFUND_LIABILITY", "REFUND_PAID", "ADJUSTMENT", "REALIZED_NET_PROFIT", name="ledger_entry_type")),
        sa.Column("currency", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("source", sa.String(128)),
        sa.Column("recipient", sa.String(128)),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "referral_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("referrer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("referred_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "referral_rewards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("referrer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("referred_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reward_currency", sa.String(16), nullable=False),
        sa.Column("reward_amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("reward_rate", sa.Numeric(8, 4), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "FROZEN", "PAID", "CANCELLED", name="referral_reward_status"), server_default="PENDING"),
        sa.Column("posting_key", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("partner_code", sa.String(64), nullable=False),
        sa.Column("external_event_id", sa.String(255), nullable=False),
        sa.Column("partner_order_id", sa.String(128)),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload_hash", sa.String(128), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), server_default="false"),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("processing_attempts", sa.Integer(), server_default="0"),
        sa.Column("processing_status", sa.Enum("PENDING", "PROCESSING", "PROCESSED", "FAILED", "DEAD_LETTER", name="webhook_processing_status"), server_default="PENDING"),
        sa.Column("processing_error", sa.Text()),
        sa.UniqueConstraint("partner_code", "external_event_id"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_role", sa.String(32)),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64)),
        sa.Column("entity_id", sa.String(128)),
        sa.Column("reason", sa.Text()),
        sa.Column("request_id", sa.String(128)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("status", sa.Enum("OPEN", "IN_REVIEW", "RESOLVED", "REJECTED", name="dispute_status"), server_default="OPEN"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_metadata", sa.JSON()),
        sa.Column("admin_notes", sa.Text()),
        sa.Column("partner_reference", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "risk_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("flag_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "RESOLVED", "DISMISSED", name="risk_flag_status"), server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )

    op.execute(
        """
        INSERT INTO partners (id, code, name, adapter_type, enabled, quote_source_type, environment)
        VALUES
        (gen_random_uuid(), 'mock_fiat', 'Mock Fiat Partner', 'mock_fiat', true, 'MOCK', 'sandbox'),
        (gen_random_uuid(), 'mock_fiat_backup', 'Mock Fiat Backup', 'mock_fiat', true, 'MOCK', 'sandbox')
        """
    )


def downgrade() -> None:
    for table in [
        "risk_flags", "disputes", "audit_logs", "webhook_events", "referral_rewards",
        "referral_relationships", "ledger_entries", "order_events", "orders",
        "payment_instructions", "quotes", "partners", "users",
    ]:
        op.drop_table(table)
    for enum in [
        "risk_flag_status", "dispute_status", "webhook_processing_status",
        "referral_reward_status", "ledger_entry_type", "order_status",
        "order_direction", "quote_source_type", "circuit_breaker_state",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
