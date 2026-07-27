"""Add UNIQUE(payment_instructions.order_id) without deleting data.

Revision ID: 0002_pi_unique
Revises: 0001_initial

If duplicate order_id rows or NULL order_id exist, upgrade FAILS with a clear
error listing conflict ids. Operators must fix data via the documented runbook
before re-running — never silent DELETE in production migrations.

Idempotent: safe when 0001's create_all already applied model UniqueConstraint.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_pi_unique"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    inspector = sa.inspect(conn)

    nulls = conn.execute(
        sa.text(
            "SELECT id FROM payment_instructions WHERE order_id IS NULL ORDER BY id LIMIT 50"
        )
    ).fetchall()
    if nulls:
        ids = ", ".join(str(r[0]) for r in nulls)
        raise RuntimeError(
            "Cannot add UNIQUE(payment_instructions.order_id): "
            f"found rows with NULL order_id. Sample ids: {ids}. "
            "Fix via deploy/runbooks/payment_instructions_cleanup.md — do not auto-delete."
        )

    if dialect == "postgresql":
        dup_sql = """
            SELECT order_id, COUNT(*) AS cnt, STRING_AGG(id, ',') AS ids
            FROM payment_instructions
            GROUP BY order_id
            HAVING COUNT(*) > 1
            LIMIT 20
        """
    else:
        dup_sql = """
            SELECT order_id, COUNT(*) AS cnt, GROUP_CONCAT(id) AS ids
            FROM payment_instructions
            GROUP BY order_id
            HAVING COUNT(*) > 1
            LIMIT 20
        """
    dupes = conn.execute(sa.text(dup_sql)).fetchall()
    if dupes:
        detail = "; ".join(f"order_id={r[0]} count={r[1]} ids={r[2]}" for r in dupes)
        raise RuntimeError(
            "Cannot add UNIQUE(payment_instructions.order_id): duplicates found. "
            f"{detail}. "
            "Fix via deploy/runbooks/payment_instructions_cleanup.md — do not auto-delete."
        )

    existing_uniques = {
        u["name"] for u in inspector.get_unique_constraints("payment_instructions")
    }
    if "uq_payment_instructions_order_id" not in existing_uniques:
        op.create_unique_constraint(
            "uq_payment_instructions_order_id",
            "payment_instructions",
            ["order_id"],
        )

    order_cols = {c["name"] for c in inspector.get_columns("orders")}
    if "idempotency_fingerprint" not in order_cols:
        op.add_column(
            "orders",
            sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    order_cols = {c["name"] for c in inspector.get_columns("orders")}
    if "idempotency_fingerprint" in order_cols:
        op.drop_column("orders", "idempotency_fingerprint")
    existing_uniques = {
        u["name"] for u in inspector.get_unique_constraints("payment_instructions")
    }
    if "uq_payment_instructions_order_id" in existing_uniques:
        op.drop_constraint(
            "uq_payment_instructions_order_id",
            "payment_instructions",
            type_="unique",
        )
