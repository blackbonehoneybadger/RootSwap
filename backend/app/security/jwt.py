"""Access-token (JWT) minting and strict verification.

Claims: iss, aud, sub, tid, iat, nbf, exp, jti, and (for tokens minted by the
real login flow) sid — the server-side auth session id. Verification always
enforces issuer, audience, and expiry, and rejects anything but the configured
algorithm.
"""

import time
import uuid

import jwt as pyjwt

from app.core.config import get_settings
from app.core.errors import AuthError


def create_access_token(
    user_id: str,
    telegram_id: int,
    role: str | None = None,
    session_id: str | None = None,
) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": user_id,
        "tid": telegram_id,
        "iat": now,
        "nbf": now,
        "exp": now + settings.jwt_ttl_seconds,
        "jti": uuid.uuid4().hex,
    }
    if role:
        payload["role"] = role
    if session_id:
        payload["sid"] = session_id
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return pyjwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={
                "require": ["exp", "iat", "nbf", "sub", "iss", "aud"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except pyjwt.PyJWTError as exc:
        raise AuthError("invalid or expired token") from exc
