"""Server-side authentication session.

The refresh token itself is an opaque random string that is NEVER stored:
only its SHA-256 hash lives here. On rotation the current hash is replaced and
the outgoing hash is remembered in ``previous_token_hash`` so that a replay of an
already-rotated token (a classic sign of token theft) is detectable and revokes
the whole session. The access JWT carries this row's ``id`` as its ``sid`` claim.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_id, utcnow


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    # SHA-256 hex of the current refresh token. Never the token itself.
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # SHA-256 hex of the immediately-previous refresh token, for replay detection.
    previous_token_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    rotation_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_auth_sessions_user_active", "user_id", "revoked_at"),
    )

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > utcnow()
