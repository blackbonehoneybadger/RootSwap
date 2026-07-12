"""Emergency stop: blocks creation of new quotes and orders when active."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import EmergencyStopError
from app.db.base import utcnow
from app.models.system_flag import SystemFlag

KEY = "emergency_stop"


async def is_active(session: AsyncSession) -> bool:
    flag = (
        await session.execute(select(SystemFlag).where(SystemFlag.key == KEY))
    ).scalar_one_or_none()
    return flag is not None and flag.value == "on"


async def ensure_not_stopped(session: AsyncSession) -> None:
    if await is_active(session):
        raise EmergencyStopError("service is temporarily paused by operations")


async def activate(session: AsyncSession, set_by: str, reason: str | None = None) -> None:
    flag = (
        await session.execute(select(SystemFlag).where(SystemFlag.key == KEY))
    ).scalar_one_or_none()
    if flag is None:
        flag = SystemFlag(key=KEY, value="on", set_by=set_by, reason=reason)
        session.add(flag)
    else:
        flag.value = "on"
        flag.set_by = set_by
        flag.reason = reason
        flag.updated_at = utcnow()
    await session.flush()


async def deactivate(session: AsyncSession, set_by: str) -> None:
    flag = (
        await session.execute(select(SystemFlag).where(SystemFlag.key == KEY))
    ).scalar_one_or_none()
    if flag is not None:
        flag.value = "off"
        flag.set_by = set_by
        flag.updated_at = utcnow()
        await session.flush()
