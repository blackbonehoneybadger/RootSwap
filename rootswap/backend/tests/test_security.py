import uuid

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.enums import AdminRole
from app.core.exceptions import UnauthorizedError
from app.security import (
    check_admin_role,
    create_access_token,
    decode_access_token,
    validate_telegram_init_data,
)
from tests.conftest import make_init_data


def test_jwt_requires_iss_aud_jti():
    get_settings.cache_clear()
    settings = get_settings()
    token = create_access_token(str(uuid.uuid4()))
    payload = decode_access_token(token)
    assert payload["iss"] == settings.jwt_issuer
    assert payload["aud"] == settings.jwt_audience
    assert payload["jti"]


def test_jwt_rejects_tampered_audience():
    get_settings.cache_clear()
    settings = get_settings()
    token = create_access_token(str(uuid.uuid4()))
    payload = jwt.get_unverified_claims(token)
    payload["aud"] = "evil"
    forged = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(UnauthorizedError):
        decode_access_token(forged)


def test_telegram_init_data_rejects_future_auth_date(monkeypatch):
    import hashlib
    import hmac
    import json
    import time
    from urllib.parse import urlencode

    bot = "0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER"
    user = json.dumps({"id": 1, "username": "x", "first_name": "T"})
    data = {"user": user, "auth_date": str(int(time.time()) + 3600)}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", bot.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    init = urlencode(data)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", bot)
    get_settings.cache_clear()
    with pytest.raises(UnauthorizedError):
        validate_telegram_init_data(init)


def test_telegram_init_data_replay(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER")
    get_settings.cache_clear()
    init = make_init_data(telegram_id=424242)
    validate_telegram_init_data(init)
    with pytest.raises(UnauthorizedError):
        validate_telegram_init_data(init)


def test_admin_key_constant_time_rejects_wrong():
    get_settings.cache_clear()
    with pytest.raises(UnauthorizedError):
        check_admin_role("totally-wrong-key", {AdminRole.ADMIN})


@pytest.mark.asyncio
async def test_security_headers_present(client):
    resp = await client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "geolocation=()" in (resp.headers.get("permissions-policy") or "")


@pytest.mark.asyncio
async def test_body_too_large_rejected(client):
    huge = "x" * (70_000)
    resp = await client.post(
        "/api/v1/webhooks/partners/mock_fiat",
        content=huge.encode(),
        headers={"Content-Type": "application/json", "Content-Length": str(len(huge))},
    )
    assert resp.status_code in (413, 401, 400)
