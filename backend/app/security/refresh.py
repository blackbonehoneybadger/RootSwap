"""Opaque refresh-token generation and hashing.

The refresh token is a high-entropy random string handed to the client only in
an HttpOnly cookie. The server stores nothing but its SHA-256 hash, so a database
leak never yields a usable token. A CSRF token is a separate high-entropy string
used for the double-submit-cookie defense on cookie-authenticated endpoints.
"""

import hashlib
import hmac
import secrets


def generate_refresh_token() -> str:
    # 48 bytes -> 64 url-safe chars of entropy.
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_matches(cookie_value: str, header_value: str) -> bool:
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)
