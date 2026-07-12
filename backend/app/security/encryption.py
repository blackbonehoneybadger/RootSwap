"""Field-level encryption for sensitive values (bank details, wallet addresses).

Uses Fernet (AES128-CBC + HMAC). In development without ENCRYPTION_KEY a key is
derived from JWT secret — production startup fails without a real key.
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings

_fernet: Fernet | None = None
_fernet_key_src: str | None = None


def _get_fernet() -> Fernet:
    global _fernet, _fernet_key_src
    settings = get_settings()
    key = settings.encryption_key
    if not key:
        # Dev/test fallback only. validate_for_production() forbids this in prod.
        key = base64.urlsafe_b64encode(
            hashlib.sha256(f"dev-{settings.jwt_secret}".encode()).digest()
        ).decode()
    if _fernet is None or _fernet_key_src != key:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        _fernet_key_src = key
    return _fernet


def encrypt_value(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
