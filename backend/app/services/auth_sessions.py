"""Server-side auth-session lifecycle: create, rotate (with replay detection),
and revoke.

Security model
--------------
* Only the SHA-256 hash of the current refresh token is stored.
* Every successful refresh ROTATES the token: a fresh opaque token is issued and
  the old hash is remembered in ``previous_token_hash``.
* If a client presents a token whose hash matches a session's
  ``previous_token_hash`` (i.e. an already-rotated token is replayed), that is
  treated as token theft: the session is revoked immediately and the refresh is
  rejected. This is the standard refresh-token-reuse detection.
* Expired or revoked sessions never rotate.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthError
from app.db.base import utcnow
from app.models.auth_session import AuthSession
from app.observability.metrics import metrics
from app.security.refresh import generate_refresh_token, hash_refresh_token
from app.services.audit import write_audit


async def create_session(
    session: AsyncSession, user_id: str
) -> tuple[AuthSession, str]:
    """Create a new auth session, returning (row, raw_refresh_token)."""
    settings = get_settings()
    raw = generate_refresh_token()
    now = utcnow()
    row = AuthSession(
        user_id=user_id,
        refresh_token_hash=hash_refresh_token(raw),
        previous_token_hash=None,
        rotation_count=0,
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(seconds=settings.refresh_ttl_seconds),
    )
    session.add(row)
    await session.flush()
    return row, raw


async def rotate_session(
    session: AsyncSession, raw_refresh_token: str
) -> tuple[AuthSession, str]:
    """Validate + rotate a refresh token. Returns (row, new_raw_token).

    Raises AuthError on any invalid/expired/revoked/replayed token.
    """
    token_hash = hash_refresh_token(raw_refresh_token)

    # 1) Current, active token -> rotate normally.
    row = (
        await session.execute(
            select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        )
    ).scalar_one_or_none()

    if row is not None:
        if row.revoked_at is not None:
            raise AuthError("session revoked")
        if row.expires_at <= utcnow():
            raise AuthError("session expired")
        new_raw = generate_refresh_token()
        row.previous_token_hash = row.refresh_token_hash
        row.refresh_token_hash = hash_refresh_token(new_raw)
        row.rotation_count += 1
        row.last_used_at = utcnow()
        await session.flush()
        return row, new_raw

    # 2) Not a current token — is it an already-rotated (stolen) one? Revoke.
    replayed = (
        await session.execute(
            select(AuthSession).where(AuthSession.previous_token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if replayed is not None and replayed.revoked_at is None:
        replayed.revoked_at = utcnow()
        replayed.revoked_reason = "refresh_token_reuse"
        metrics.inc("auth_refresh_reuse_detected_total")
        write_audit(
            session,
            action="auth.session.reuse_detected",
            entity_type="auth_session",
            entity_id=replayed.id,
            metadata={"user_id": replayed.user_id},
        )
        # The revocation MUST survive even though this request fails: the caller
        # raises before its own commit, so persist the theft response here.
        await session.commit()
        raise AuthError("refresh token reuse detected; session revoked")

    metrics.inc("auth_refresh_invalid_total")
    raise AuthError("invalid refresh token")


async def revoke_session(
    session: AsyncSession, raw_refresh_token: str, reason: str = "logout"
) -> bool:
    """Revoke the session that owns this refresh token. Idempotent."""
    token_hash = hash_refresh_token(raw_refresh_token)
    row = (
        await session.execute(
            select(AuthSession).where(
                (AuthSession.refresh_token_hash == token_hash)
                | (AuthSession.previous_token_hash == token_hash)
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        row.revoked_reason = reason
        await session.flush()
    return True
