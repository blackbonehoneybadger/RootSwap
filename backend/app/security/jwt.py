import time

import jwt as pyjwt

from app.core.config import get_settings
from app.core.errors import AuthError


def create_access_token(user_id: str, telegram_id: int, role: str | None = None) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": user_id,
        "tid": telegram_id,
        "iat": now,
        "exp": now + settings.jwt_ttl_seconds,
        "iss": "rootswap",
    }
    if role:
        payload["role"] = role
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return pyjwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer="rootswap",
        )
    except pyjwt.PyJWTError as exc:
        raise AuthError("invalid or expired token") from exc
