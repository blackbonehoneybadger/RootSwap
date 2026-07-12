from sqlalchemy import select

from app.models.referral import ReferralRelationship
from app.models.user import User
from tests.conftest import authed_user, make_init_data


async def test_telegram_auth_creates_user(client, session):
    headers, user = await authed_user(client, telegram_id=111)
    assert user["telegram_id"] == 111
    assert user["referral_code"]
    row = (
        await session.execute(select(User).where(User.telegram_id == 111))
    ).scalar_one()
    assert row.username == "testuser"


async def test_telegram_auth_rejects_bad_signature(client):
    init_data = make_init_data(telegram_id=112, bot_token="9999:wrong-token")
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": init_data})
    assert resp.status_code == 401


async def test_telegram_auth_rejects_garbage(client):
    resp = await client.post("/api/v1/auth/telegram", json={"init_data": "hash=zzz"})
    assert resp.status_code == 401


async def test_auth_is_idempotent(client, session):
    await authed_user(client, telegram_id=113)
    await authed_user(client, telegram_id=113)
    rows = (
        (await session.execute(select(User).where(User.telegram_id == 113))).scalars().all()
    )
    assert len(rows) == 1


async def test_referral_start_param_attaches_referrer(client, session):
    _, referrer = await authed_user(client, telegram_id=114)
    _, referred = await authed_user(
        client, telegram_id=115, start_param=f"ref_{referrer['referral_code']}"
    )
    rel = (
        await session.execute(
            select(ReferralRelationship).where(
                ReferralRelationship.referred_user_id == referred["id"]
            )
        )
    ).scalar_one()
    assert rel.referrer_user_id == referrer["id"]


async def test_self_referral_forbidden(client, session):
    # user registers with their own (not yet existing) code -> no relationship
    _, user = await authed_user(client, telegram_id=116)
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={
            "init_data": make_init_data(telegram_id=116),
            "referral_code": user["referral_code"],
        },
    )
    assert resp.status_code == 200
    rel = (
        await session.execute(
            select(ReferralRelationship).where(
                ReferralRelationship.referred_user_id == user["id"]
            )
        )
    ).scalar_one_or_none()
    assert rel is None


async def test_referrer_set_only_once(client, session):
    _, ref_a = await authed_user(client, telegram_id=117)
    _, ref_b = await authed_user(client, telegram_id=118)
    _, referred = await authed_user(
        client, telegram_id=119, start_param=f"ref_{ref_a['referral_code']}"
    )
    # second auth with another code must not change the referrer
    resp = await client.post(
        "/api/v1/auth/telegram",
        json={
            "init_data": make_init_data(telegram_id=119),
            "referral_code": ref_b["referral_code"],
        },
    )
    assert resp.status_code == 200
    row = (
        await session.execute(select(User).where(User.id == referred["id"]))
    ).scalar_one()
    assert row.referred_by_user_id == ref_a["id"]


async def test_protected_endpoint_requires_token(client):
    resp = await client.get("/api/v1/orders")
    assert resp.status_code == 401
