import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthError, ForbiddenError
from app.db.session import get_db
from app.models.user import User
from app.schemas.api import (
    LogoutResponse,
    RefreshResponse,
    TelegramAuthRequest,
    TelegramAuthResponse,
    UserOut,
)
from app.security.jwt import create_access_token
from app.security.rbac import resolve_admin_role
from app.security.refresh import csrf_matches, generate_csrf_token
from app.security.telegram import validate_init_data
from app.services.auth_sessions import (
    create_session,
    revoke_session,
    rotate_session,
)
from app.services.referral import attach_referrer, generate_referral_code

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _set_auth_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    settings = get_settings()
    # Refresh token: HttpOnly (JS can never read it), scoped to the auth path so
    # it is only sent to /auth/refresh and /auth/logout.
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_ttl_seconds,
        path=f"{settings.api_v1_prefix}/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    # CSRF token: readable by JS for the double-submit header.
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=settings.refresh_ttl_seconds,
        path="/",
        secure=settings.cookie_secure,
        httponly=False,
        samesite=settings.cookie_samesite,
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=f"{settings.api_v1_prefix}/auth",
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        httponly=True,
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )


def _require_csrf(request: Request) -> None:
    settings = get_settings()
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    header = request.headers.get("x-csrf-token", "")
    if not csrf_matches(cookie, header):
        raise ForbiddenError("CSRF token missing or invalid")


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        referral_code=user.referral_code,
    )


@router.post("/telegram", response_model=TelegramAuthResponse)
async def telegram_auth(
    body: TelegramAuthRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TelegramAuthResponse:
    parsed = validate_init_data(body.init_data)
    tg_user = parsed["user"]
    telegram_id = int(tg_user["id"])

    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    created = False
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            referral_code=generate_referral_code(),
        )
        session.add(user)
        await session.flush()
        created = True
    else:
        user.username = tg_user.get("username") or user.username
        user.first_name = tg_user.get("first_name") or user.first_name

    if user.is_blocked:
        raise ForbiddenError("account is blocked")

    referral_code = body.referral_code
    start_param = parsed.get("start_param") or ""
    if not referral_code and start_param.startswith("ref_"):
        referral_code = start_param.removeprefix("ref_")
    if created and referral_code:
        await attach_referrer(session, user, referral_code)

    auth_session, refresh_token = await create_session(session, user.id)
    csrf_token = generate_csrf_token()
    await session.commit()

    role = resolve_admin_role(telegram_id)
    token = create_access_token(
        user.id, telegram_id, role.value if role else None, session_id=auth_session.id
    )
    _set_auth_cookies(response, refresh_token, csrf_token)
    logger.info(
        "telegram auth ok",
        extra={"ctx": {"user_id": user.id, "created": created}},
    )
    return TelegramAuthResponse(
        access_token=token, csrf_token=csrf_token, user=_user_out(user)
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    settings = get_settings()
    _require_csrf(request)
    refresh_cookie = request.cookies.get(settings.refresh_cookie_name, "")
    if not refresh_cookie:
        raise AuthError("no refresh token")

    auth_session, new_refresh = await rotate_session(session, refresh_cookie)
    user = (
        await session.execute(
            select(User).where(User.id == auth_session.user_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise AuthError("user not found")
    if user.is_blocked:
        raise ForbiddenError("account is blocked")

    csrf_token = generate_csrf_token()
    await session.commit()

    role = resolve_admin_role(user.telegram_id)
    token = create_access_token(
        user.id, user.telegram_id, role.value if role else None,
        session_id=auth_session.id,
    )
    _set_auth_cookies(response, new_refresh, csrf_token)
    return RefreshResponse(
        access_token=token, csrf_token=csrf_token, user=_user_out(user)
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    settings = get_settings()
    _require_csrf(request)
    refresh_cookie = request.cookies.get(settings.refresh_cookie_name, "")
    if refresh_cookie:
        await revoke_session(session, refresh_cookie, reason="logout")
        await session.commit()
    _clear_auth_cookies(response)
    return LogoutResponse(ok=True)
