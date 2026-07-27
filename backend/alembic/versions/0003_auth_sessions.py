"""Add auth_sessions (server-side refresh-token sessions).

Idempotent, mirroring 0002: because 0001 builds the schema from live
SQLAlchemy metadata via create_all, a from-empty upgrade already materializes
auth_sessions here. This migration therefore only creates the table/indexes when
they are absent, so it is correct both from empty (no-op) and against a database
created by an older 0001 that predates this table (real create).
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_auth_sessions"
down_revision = "0002_pi_unique"
branch_labels = None
depends_on = None

_TABLE = "auth_sessions"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _TABLE not in inspector.get_table_names():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(length=36),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
            sa.Column("previous_token_hash", sa.String(length=64), nullable=True),
            sa.Column("rotation_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_reason", sa.String(length=64), nullable=True),
        )

    existing_indexes = {i["name"] for i in inspector.get_indexes(_TABLE)} if (
        _TABLE in inspector.get_table_names()
    ) else set()
    existing_uniques = {
        u["name"] for u in inspector.get_unique_constraints(_TABLE)
    } if _TABLE in inspector.get_table_names() else set()

    # A unique index on the current hash may materialize either as a unique
    # index or a unique constraint depending on how the table was built.
    has_hash_unique = (
        "ix_auth_sessions_refresh_token_hash" in existing_indexes
        or "uq_auth_sessions_refresh_token_hash" in existing_uniques
    )
    if not has_hash_unique:
        op.create_index(
            "ix_auth_sessions_refresh_token_hash",
            _TABLE,
            ["refresh_token_hash"],
            unique=True,
        )
    if "ix_auth_sessions_previous_token_hash" not in existing_indexes:
        op.create_index(
            "ix_auth_sessions_previous_token_hash",
            _TABLE,
            ["previous_token_hash"],
        )
    if "ix_auth_sessions_user_id" not in existing_indexes:
        op.create_index("ix_auth_sessions_user_id", _TABLE, ["user_id"])
    if "ix_auth_sessions_user_active" not in existing_indexes:
        op.create_index(
            "ix_auth_sessions_user_active", _TABLE, ["user_id", "revoked_at"]
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
