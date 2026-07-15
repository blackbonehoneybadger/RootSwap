"""Drop circular FK from orders.payment_instructions_id.

Revision ID: 002_drop_orders_pi_fk
Revises: 001_initial
Create Date: 2026-07-15

Root cause: orders.payment_instructions_id → payment_instructions.id AND
payment_instructions.order_id → orders.id formed a non-deferrable circular FK.
PostgreSQL rejected inserts during order creation; SQLite tests did not catch it.

Fix: keep payment_instructions.order_id as the owning FK; keep
orders.payment_instructions_id as a nullable soft pointer without a DB FK.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_drop_orders_pi_fk"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: drop any FK on orders that references payment_instructions.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            WHERE rel.relname = 'orders'
              AND con.contype = 'f'
              AND pg_get_constraintdef(con.oid) LIKE '%payment_instructions%'
            """
        )
    ).fetchall()
    for (conname,) in rows:
        op.drop_constraint(conname, "orders", type_="foreignkey")


def downgrade() -> None:
    # Reconstruct circular FK only for rollback testing; not recommended for use.
    op.create_foreign_key(
        "orders_payment_instructions_id_fkey",
        "orders",
        "payment_instructions",
        ["payment_instructions_id"],
        ["id"],
    )
