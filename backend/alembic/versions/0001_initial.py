"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-12

Creates the full RootSwap schema from SQLAlchemy metadata. This is the first
migration; subsequent schema changes must be expressed as explicit alembic
operations.
"""

from alembic import op

from app.db.base import Base
from app import models  # noqa: F401  # register all models on Base.metadata

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
