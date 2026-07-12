from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdminRole
from app.core.errors import AuthError, ForbiddenError
from app.db.session import get_db
from app.models.user import User
from app.security.jwt import decode_access_token
from app.security.rbac import require_role


async def get_current_user(
    authorization: str = Header(default=""),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise AuthError("missing bearer token")
    payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    user = (
        await session.execute(select(User).where(User.id == payload["sub"]))
    ).scalar_one_or_none()
    if user is None:
        raise AuthError("user not found")
    if user.is_blocked:
        raise ForbiddenError("account is blocked")
    return user


class AdminContext:
    def __init__(self, user: User, role: AdminRole):
        self.user = user
        self.role = role


def admin_required(minimum: AdminRole):
    async def dependency(
        authorization: str = Header(default=""),
        session: AsyncSession = Depends(get_db),
    ) -> AdminContext:
        if not authorization.startswith("Bearer "):
            raise AuthError("missing bearer token")
        payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
        role_raw = payload.get("role")
        role = None
        if role_raw:
            try:
                role = AdminRole(role_raw)
            except ValueError:
                role = None
        require_role(role, minimum)
        user = (
            await session.execute(select(User).where(User.id == payload["sub"]))
        ).scalar_one_or_none()
        if user is None:
            raise AuthError("user not found")
        return AdminContext(user, role)

    return dependency
