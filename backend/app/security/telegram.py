"""Telegram Mini App initData HMAC validation.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
hash = hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from app.core.config import get_settings
from app.core.errors import AuthError


def build_data_check_string(pairs: dict[str, str]) -> str:
    return "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()) if k != "hash")


def compute_init_data_hash(pairs: dict[str, str], bot_token: str) -> str:
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    dcs = build_data_check_string(pairs)
    return hmac.new(secret_key, dcs.encode(), hashlib.sha256).hexdigest()


def validate_init_data(init_data: str) -> dict:
    """Validate raw initData query string, return parsed telegram user payload."""
    settings = get_settings()
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception as exc:  # pragma: no cover - parse_qsl rarely raises
        raise AuthError("malformed initData") from exc

    if "user" not in pairs:
        raise AuthError("initData has no user")

    if settings.telegram_auth_insecure_skip and not settings.is_production:
        pass  # dev-only escape hatch
    else:
        if not settings.telegram_bot_token:
            raise AuthError("bot token is not configured")
        provided_hash = pairs.get("hash", "")
        expected = compute_init_data_hash(pairs, settings.telegram_bot_token)
        if not provided_hash or not hmac.compare_digest(provided_hash, expected):
            raise AuthError("initData signature mismatch")
        auth_date = int(pairs.get("auth_date", "0") or "0")
        if auth_date and time.time() - auth_date > settings.telegram_auth_max_age_seconds:
            raise AuthError("initData expired")

    try:
        user = json.loads(pairs["user"])
    except (ValueError, KeyError) as exc:
        raise AuthError("initData user is not valid JSON") from exc
    if "id" not in user:
        raise AuthError("initData user has no id")
    return {
        "user": user,
        "start_param": pairs.get("start_param", ""),
        "auth_date": pairs.get("auth_date"),
    }
