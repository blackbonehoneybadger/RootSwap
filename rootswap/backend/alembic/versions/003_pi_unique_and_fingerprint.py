"""Enforce 1:1 PaymentInstructions and idempotency fingerprint.

Revision ID: 003_pi_unique_fingerprint
Revises: 002_drop_orders_pi_fk
Create Date: 2026-07-15

- UNIQUE(payment_instructions.order_id) — at most one PI per order
- order_id NOT NULL on payment_instructions
- orders.idempotency_fingerprint for payload conflict detection

Idempotent for DBs whose 001 already created the unique constraint /
fingerprint column (updated scaffold).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_pi_unique_fingerprint"
down_revision = "002_drop_orders_pi_fk"
branch_labels = None
depends_on = None


def _has_unique(bind, table: str, name: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conname = :name
              AND contype = 'u'
            """
        ),
        {"name": name},
    ).fetchone()
    return row is not None


def _has_column(bind, table: str, column: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()

    op.execute(
        sa.text(
            """
            DELETE FROM payment_instructions
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY order_id ORDER BY created_at ASC NULLS LAST, id ASC
                           ) AS rn
                    FROM payment_instructions
                    WHERE order_id IS NOT NULL
                ) ranked
                WHERE rn > 1
            )
            """
        )
    )
    op.execute(sa.text("DELETE FROM payment_instructions WHERE order_id IS NULL"))

    op.alter_column(
        "payment_instructions",
        "order_id",
        existing_type=sa.UUID(),
        nullable=False,
    )

    if not _has_unique(bind, "payment_instructions", "uq_payment_instructions_order_id"):
        op.create_unique_constraint(
            "uq_payment_instructions_order_id",
            "payment_instructions",
            ["order_id"],
        )

    if not _has_column(bind, "orders", "idempotency_fingerprint"):
        op.add_column(
            "orders",
            sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "orders", "idempotency_fingerprint"):
        op.drop_column("orders", "idempotency_fingerprint")
    if _has_unique(bind, "payment_instructions", "uq_payment_instructions_order_id"):
        op.drop_constraint(
            "uq_payment_instructions_order_id",
            "payment_instructions",
            type_="unique",
        )
    op.alter_column(
        "payment_instructions",
        "order_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
