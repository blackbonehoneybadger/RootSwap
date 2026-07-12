import uuid

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AdminRole
from app.core.exceptions import DomainError, UnauthorizedError
from app.db.session import get_db
from app.models import User
from app.security import check_admin_role, decode_access_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.is_blocked:
        raise HTTPException(status_code=401, detail="User not found or blocked")
    return user


def require_admin(*roles: AdminRole):
    async def dependency(x_admin_key: str | None = Header(None, alias="X-Admin-Key")) -> AdminRole:
        if not x_admin_key:
            raise HTTPException(status_code=401, detail="Admin key required")
        try:
            required = set(roles) if roles else {AdminRole.ADMIN}
            return check_admin_role(x_admin_key, required)
        except UnauthorizedError as exc:
            raise HTTPException(status_code=403, detail=exc.message) from exc

    return dependency


def domain_error_handler(exc: DomainError) -> HTTPException:
    status_map = {
        "not_found": 404,
        "forbidden": 403,
        "unauthorized": 401,
        "validation_error": 400,
        "conflict": 409,
        "emergency_stop": 503,
        "invalid_transition": 400,
    }
    return HTTPException(status_code=status_map.get(exc.code, 400), detail=exc.message)
