from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.request_id import request_id_var
from app.models.audit_log import AuditLog


def write_audit(
    session: AsyncSession,
    action: str,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        request_id=request_id_var.get(),
        ip_address=ip_address,
        metadata_=metadata,
    )
    session.add(entry)
    return entry
