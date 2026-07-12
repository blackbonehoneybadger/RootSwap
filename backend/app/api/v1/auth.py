import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.api import TelegramAuthRequest, TelegramAuthResponse, UserOut
from app.security.jwt import create_access_token
from app.security.rbac import resolve_admin_role
from app.security.telegram import validate_init_data
from app.services.referral import attach_referrer, generate_referral_code

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/telegram", response_model=TelegramAuthResponse)
async def telegram_auth(
    body: TelegramAuthRequest, session: AsyncSession = Depends(get_db)
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

    referral_code = body.referral_code
    start_param = parsed.get("start_param") or ""
    if not referral_code and start_param.startswith("ref_"):
        referral_code = start_param.removeprefix("ref_")
    if created and referral_code:
        await attach_referrer(session, user, referral_code)

    await session.commit()

    role = resolve_admin_role(telegram_id)
    token = create_access_token(user.id, telegram_id, role.value if role else None)
    logger.info(
        "telegram auth ok",
        extra={"ctx": {"user_id": user.id, "created": created}},
    )
    return TelegramAuthResponse(
        access_token=token,
        user=UserOut(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            referral_code=user.referral_code,
        ),
    )
