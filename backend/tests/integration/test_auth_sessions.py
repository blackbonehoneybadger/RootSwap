"""Server-side session + refresh-token rotation, CSRF, logout, reuse detection."""

import jwt as pyjwt
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.auth_session import AuthSession
from app.security.jwt import decode_access_token
from tests.conftest import make_init_data


async def _login(client, telegram_id=5001):
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": make_init_data(telegram_id=telegram_id)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    refresh = resp.cookies.get("rs_refresh")
    assert refresh, "login must set the refresh cookie"
    return data, refresh


def _refresh(client, refresh_token: str, csrf: str):
    return client.post(
        "/api/v1/auth/refresh",
        cookies={"rs_refresh": refresh_token, "rs_csrf": csrf},
        headers={"X-CSRF-Token": csrf},
    )


async def test_login_sets_httponly_refresh_cookie_and_claims(client):
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={"init_data": make_init_data(telegram_id=5100)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Access token carries the hardened claim set incl. the session id.
    claims = decode_access_token(data["access_token"])
    for required in ("iss", "aud", "sub", "tid", "iat", "nbf", "exp", "jti", "sid"):
        assert required in claims, f"missing claim {required}"

    # The refresh cookie must be HttpOnly (never readable by JS); the CSRF
    # cookie must NOT be (the frontend has to read it for the double-submit).
    set_cookies = resp.headers.get_list("set-cookie")
    refresh_cookie = next(c for c in set_cookies if c.startswith("rs_refresh="))
    csrf_cookie = next(c for c in set_cookies if c.startswith("rs_csrf="))
    assert "httponly" in refresh_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()


async def test_refresh_rotates_and_returns_new_access_token(client, session):
    data, refresh_v0 = await _login(client, telegram_id=5101)
    csrf = data["csrf_token"]

    r1 = await _refresh(client, refresh_v0, csrf)
    assert r1.status_code == 200, r1.text
    refresh_v1 = r1.cookies.get("rs_refresh")
    assert refresh_v1 and refresh_v1 != refresh_v0, "refresh must rotate the token"

    # new access token is valid and independent
    new_claims = decode_access_token(r1.json()["access_token"])
    assert new_claims["sub"] == data["user"]["id"]

    # exactly one session row, rotation_count advanced
    rows = (await session.execute(select(AuthSession))).scalars().all()
    assert len(rows) == 1
    assert rows[0].rotation_count == 1


async def test_refresh_requires_csrf(client):
    data, refresh_v0 = await _login(client, telegram_id=5102)
    # cookie present but no X-CSRF-Token header -> rejected
    resp = await client.post(
        "/api/v1/auth/refresh",
        cookies={"rs_refresh": refresh_v0, "rs_csrf": data["csrf_token"]},
    )
    assert resp.status_code == 403, resp.text


async def test_refresh_csrf_mismatch_rejected(client):
    data, refresh_v0 = await _login(client, telegram_id=5103)
    resp = await client.post(
        "/api/v1/auth/refresh",
        cookies={"rs_refresh": refresh_v0, "rs_csrf": data["csrf_token"]},
        headers={"X-CSRF-Token": "not-the-cookie-value"},
    )
    assert resp.status_code == 403, resp.text


async def test_reuse_of_rotated_token_revokes_session(client, session):
    data, refresh_v0 = await _login(client, telegram_id=5104)
    csrf = data["csrf_token"]

    r1 = await _refresh(client, refresh_v0, csrf)
    assert r1.status_code == 200
    refresh_v1 = r1.cookies.get("rs_refresh")
    csrf1 = r1.json()["csrf_token"]

    # Replay the OLD, already-rotated token -> theft signal -> 401 + revoke.
    replay = await _refresh(client, refresh_v0, csrf)
    assert replay.status_code == 401, replay.text

    # Even the legitimate latest token is now dead (whole session revoked).
    after = await _refresh(client, refresh_v1, csrf1)
    assert after.status_code == 401, after.text

    row = (await session.execute(select(AuthSession))).scalar_one()
    assert row.revoked_at is not None
    assert row.revoked_reason == "refresh_token_reuse"


async def test_logout_revokes_session(client, session):
    data, refresh_v0 = await _login(client, telegram_id=5105)
    csrf = data["csrf_token"]

    out = await client.post(
        "/api/v1/auth/logout",
        cookies={"rs_refresh": refresh_v0, "rs_csrf": csrf},
        headers={"X-CSRF-Token": csrf},
    )
    assert out.status_code == 200, out.text

    # the refresh token no longer works
    resp = await _refresh(client, refresh_v0, csrf)
    assert resp.status_code == 401

    row = (await session.execute(select(AuthSession))).scalar_one()
    assert row.revoked_at is not None
    assert row.revoked_reason == "logout"


async def test_refresh_with_unknown_token_is_401(client):
    data, _ = await _login(client, telegram_id=5106)
    csrf = data["csrf_token"]
    resp = await _refresh(client, "totally-invalid-token", csrf)
    assert resp.status_code == 401


async def test_access_token_wrong_audience_rejected(client):
    settings = get_settings()
    import time

    now = int(time.time())
    bad = pyjwt.encode(
        {
            "iss": settings.jwt_issuer,
            "aud": "some-other-app",
            "sub": "x",
            "tid": 1,
            "iat": now,
            "nbf": now,
            "exp": now + 60,
            "jti": "abc",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    resp = await client.get("/api/v1/orders", headers={"Authorization": f"Bearer {bad}"})
    assert resp.status_code == 401


async def test_only_one_session_per_login(client, session):
    await _login(client, telegram_id=5107)
    await _login(client, telegram_id=5107)
    # two logins -> two independent sessions for the same user
    n = (
        await session.execute(select(func.count()).select_from(AuthSession))
    ).scalar_one()
    assert n == 2
