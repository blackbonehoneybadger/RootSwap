from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.referral import get_stats

router = APIRouter(prefix="/referral", tags=["referral"])


@router.get("/stats")
async def referral_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await get_stats(session, user)
