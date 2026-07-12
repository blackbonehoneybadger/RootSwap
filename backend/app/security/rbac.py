"""Admin RBAC.

Admin roles are assigned via ADMIN_TELEGRAM_IDS setting (JSON: telegram_id -> role).
JWTs for admins carry a `role` claim. Endpoint dependencies declare a minimum role.
"""

import json

from app.core.config import get_settings
from app.core.enums import ADMIN_ROLE_RANK, AdminRole
from app.core.errors import ForbiddenError


def resolve_admin_role(telegram_id: int) -> AdminRole | None:
    try:
        mapping = json.loads(get_settings().admin_telegram_ids or "{}")
    except ValueError:
        return None
    raw = mapping.get(str(telegram_id))
    if raw is None:
        return None
    try:
        return AdminRole(raw.upper())
    except ValueError:
        return None


def require_role(actual: AdminRole | None, minimum: AdminRole) -> None:
    if actual is None or ADMIN_ROLE_RANK[actual] < ADMIN_ROLE_RANK[minimum]:
        raise ForbiddenError(f"requires role {minimum.value} or higher")
