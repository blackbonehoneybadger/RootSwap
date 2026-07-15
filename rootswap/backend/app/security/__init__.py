"""Security helpers: JWT, Telegram initData, encryption, admin keys, wallets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl

from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.enums import AdminRole
from app.core.exceptions import UnauthorizedError, ValidationError

SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{16,19}\b"),
    re.compile(r"\b\d{20}\b"),
    re.compile(r"bc1[a-z0-9]{25,87}", re.I),
    re.compile(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}"),
    re.compile(r"4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}"),
    re.compile(r"T[A-Za-z1-9]{33}"),
]

ALLOWED_JWT_ALGORITHMS = ("HS256",)


def _fernet() -> Fernet:
    key = hashlib.sha256(get_settings().encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_value(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def mask_string(value: str, visible_start: int = 4, visible_end: int = 4) -> str:
    if len(value) <= visible_start + visible_end:
        return "*" * len(value)
    return (
        value[:visible_start]
        + "*" * (len(value) - visible_start - visible_end)
        + value[-visible_end:]
    )


def mask_sensitive_data(data: Any) -> Any:
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            kl = k.lower()
            if any(
                s in kl
                for s in (
                    "encrypted",
                    "secret",
                    "password",
                    "token",
                    "private",
                    "authorization",
                    "init_data",
                    "cookie",
                    "api_key",
                )
            ):
                masked[k] = "***"
            elif any(
                s in kl
                for s in ("card", "account", "phone", "wallet", "address", "recipient")
            ):
                masked[k] = mask_string(str(v)) if v else v
            else:
                masked[k] = mask_sensitive_data(v)
        return masked
    if isinstance(data, list):
        return [mask_sensitive_data(i) for i in data]
    if isinstance(data, str):
        result = data
        for pattern in SENSITIVE_PATTERNS:
            result = pattern.sub(lambda m: mask_string(m.group(0)), result)
        return result
    return data


def create_access_token(subject: str, extra: dict | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "jti": str(uuid.uuid4()),
        "exp": expire,
        **(extra or {}),
    }
    alg = settings.jwt_algorithm
    if alg not in ALLOWED_JWT_ALGORITHMS:
        raise UnauthorizedError("Unsupported JWT algorithm configuration")
    return jwt.encode(payload, settings.jwt_secret, algorithm=alg)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    alg = settings.jwt_algorithm
    if alg not in ALLOWED_JWT_ALGORITHMS:
        raise UnauthorizedError("Unsupported JWT algorithm configuration")
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=list(ALLOWED_JWT_ALGORITHMS),
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={
                "require_exp": True,
                "require_iat": True,
                "require_sub": True,
                "require_aud": True,
            },
        )
    except JWTError as exc:
        raise UnauthorizedError("Invalid token") from exc


def _mark_init_data_used(digest: str, ttl: int) -> bool:
    """Return True if this initData hash is new; False if replay."""
    try:
        import redis

        settings = get_settings()
        client = redis.from_url(settings.redis_url, decode_responses=True)
        key = f"tg_init:{digest}"
        # SET NX — only succeed once within TTL
        return bool(client.set(key, "1", nx=True, ex=max(ttl, 60)))
    except Exception:
        # If Redis is down in development, skip replay store; elsewhere prefer fail-closed
        if get_settings().environment == "development":
            return True
        raise UnauthorizedError("Auth replay store unavailable") from None


def validate_telegram_init_data(init_data: str, bot_token: str | None = None) -> dict:
    settings = get_settings()
    token = bot_token or settings.telegram_bot_token
    if len(init_data) > settings.max_init_data_bytes:
        raise UnauthorizedError("initData too large")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise UnauthorizedError("Missing hash in initData")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        raise UnauthorizedError("Invalid Telegram initData signature")

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError as exc:
        raise UnauthorizedError("Invalid auth_date") from exc

    now = datetime.now(UTC).timestamp()
    max_age = settings.telegram_init_data_max_age_seconds
    skew = settings.telegram_init_data_clock_skew_seconds
    if auth_date <= 0:
        raise UnauthorizedError("Missing auth_date")
    if auth_date > now + skew:
        raise UnauthorizedError("Telegram initData auth_date in the future")
    if now - auth_date > max_age:
        raise UnauthorizedError("Telegram initData expired")

    # Replay protection: same signed payload cannot mint tokens twice within TTL
    digest = hashlib.sha256(f"{received_hash}:{auth_date}".encode()).hexdigest()
    if not _mark_init_data_used(digest, max_age + skew):
        raise UnauthorizedError("Telegram initData replay detected")

    user_data = parsed.get("user")
    if user_data:
        parsed["user"] = json.loads(user_data)
    return parsed


def generate_referral_code() -> str:
    return secrets.token_hex(4).upper()


def hash_payload(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def signed_webhook_message(timestamp: str, body: bytes) -> bytes:
    """Canonical message: timestamp + '.' + raw body (binds time into HMAC)."""
    return timestamp.encode() + b"." + body


# Wallet validation
BTC_BECH32 = re.compile(r"^(bc1)[a-z0-9]{25,87}$")
BTC_LEGACY = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$")
XMR_ADDRESS = re.compile(r"^4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}$")
TRON_ADDRESS = re.compile(r"^T[A-Za-z1-9]{33}$")
ERC20_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")

ASSET_NETWORK_MAP = {
    ("BTC", "BTC"): "btc",
    ("XMR", "XMR"): "xmr",
    ("USDT", "TRC20"): "trc20",
    ("USDT", "ERC20"): "erc20",
    ("RUB", None): "fiat",
    ("RUB", ""): "fiat",
}


def validate_wallet_address(asset: str, network: str | None, address: str) -> None:
    asset = asset.upper()
    network = (network or "").upper() or None
    key = (asset, network)
    if key not in ASSET_NETWORK_MAP and (asset, None) not in ASSET_NETWORK_MAP:
        raise ValidationError(f"Incompatible asset/network: {asset}/{network}")

    if asset == "BTC" and network == "BTC":
        if not (BTC_BECH32.match(address) or BTC_LEGACY.match(address)):
            raise ValidationError("Invalid BTC address")
    elif asset == "XMR" and network == "XMR":
        if not XMR_ADDRESS.match(address):
            raise ValidationError("Invalid XMR address")
    elif asset == "USDT" and network == "TRC20":
        if not TRON_ADDRESS.match(address):
            raise ValidationError("Invalid USDT TRC20 address")
    elif asset == "USDT" and network == "ERC20":
        if not ERC20_ADDRESS.match(address):
            raise ValidationError("Invalid USDT ERC20 address")
    elif asset == "RUB":
        return
    else:
        raise ValidationError(f"Unsupported wallet validation for {asset}/{network}")


def check_admin_role(api_key: str, required_roles: set[AdminRole]) -> AdminRole:
    settings = get_settings()
    if not api_key or len(api_key) > 256:
        raise UnauthorizedError("Invalid admin API key")

    def _key_digest(value: str) -> bytes:
        return hashlib.sha256(value.encode()).digest()

    matched = None
    api_digest = _key_digest(api_key)
    for stored_key, entry in settings.admin_keys_map.items():
        if hmac.compare_digest(_key_digest(stored_key), api_digest):
            matched = entry
            break
    if matched is None:
        hmac.compare_digest(_key_digest(""), api_digest)
        raise UnauthorizedError("Invalid admin API key")
    try:
        role = AdminRole(matched.role.upper())
    except ValueError as exc:
        raise UnauthorizedError("Invalid admin role") from exc
    if role == AdminRole.ADMIN:
        return role
    if role not in required_roles:
        raise UnauthorizedError("Insufficient permissions")
    return role
