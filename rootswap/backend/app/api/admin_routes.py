import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import domain_error_handler, require_admin
from app.core.config import get_settings
from app.core.enums import ActorType, AdminRole, OrderStatus
from app.core.exceptions import DomainError
from app.db.session import get_db
from app.models import AuditLog, Dispute, Order, Partner, RiskFlag, WebhookEvent
from app.observability.metrics import EMERGENCY_STOP
from app.schemas import (
    AdminDisablePartnerRequest,
    AdminRefundRequest,
    AdminTransitionRequest,
    OrderResponse,
)
from app.services.ledger import LedgerService
from app.services.order_orchestrator import OrderOrchestrator

router = APIRouter(prefix="/api/v1/admin")


async def _audit(
    session: AsyncSession,
    role: AdminRole,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    reason: str | None = None,
    request: Request | None = None,
    metadata: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_role=role.value,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            request_id=request.headers.get("X-Request-ID") if request else None,
            ip_address=request.client.host if request and request.client else None,
            metadata_=metadata,
        )
    )


@router.get("/orders", response_model=list[OrderResponse])
async def admin_list_orders(
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.SUPPORT, AdminRole.OPERATIONS, AdminRole.ADMIN)),
):
    result = await session.execute(
        select(Order).options(selectinload(Order.payment_instructions)).order_by(Order.created_at.desc())
    )
    return [OrderResponse.model_validate(o) for o in result.scalars().all()]


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def admin_get_order(
    order_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.SUPPORT, AdminRole.OPERATIONS, AdminRole.ADMIN)),
):
    result = await session.execute(
        select(Order).where(Order.id == order_id).options(selectinload(Order.payment_instructions))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.model_validate(order)


@router.post("/orders/{order_id}/transition")
async def admin_transition(
    order_id: uuid.UUID,
    body: AdminTransitionRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.OPERATIONS, AdminRole.ADMIN)),
):
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    orchestrator = OrderOrchestrator()
    try:
        await orchestrator.transition(
            session,
            order,
            body.target_status,
            ActorType.ADMIN,
            role.value,
            {"reason": body.reason},
            body.expected_version,
        )
    except DomainError as exc:
        await _audit(session, role, "transition_denied", "order", str(order_id), str(exc), request)
        raise domain_error_handler(exc) from exc
    await _audit(session, role, "transition", "order", str(order_id), body.reason, request)
    return {"status": order.status.value, "version": order.version}


@router.post("/orders/{order_id}/refund")
async def admin_refund(
    order_id: uuid.UUID,
    body: AdminRefundRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.FINANCE, AdminRole.ADMIN)),
):
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    orchestrator = OrderOrchestrator()
    ledger = LedgerService()
    try:
        await orchestrator.transition(
            session, order, OrderStatus.REFUND_REQUESTED, ActorType.ADMIN, role.value, {}
        )
        await orchestrator.transition(
            session, order, OrderStatus.REFUND_PROCESSING, ActorType.ADMIN, role.value, {}
        )
        await ledger.post_refund(session, order, body.amount)
        await orchestrator.transition(
            session, order, OrderStatus.REFUNDED, ActorType.ADMIN, role.value, {}
        )
    except DomainError as exc:
        raise domain_error_handler(exc) from exc
    await _audit(session, role, "refund", "order", str(order_id), body.reason, request)
    return {"status": order.status.value}


@router.post("/orders/{order_id}/dispute")
async def admin_dispute(
    order_id: uuid.UUID,
    reason: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.SUPPORT, AdminRole.ADMIN)),
):
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    session.add(Dispute(order_id=order.id, user_id=order.user_id, reason=reason))
    orchestrator = OrderOrchestrator()
    try:
        await orchestrator.transition(
            session, order, OrderStatus.DISPUTED, ActorType.ADMIN, role.value, {"reason": reason}
        )
    except DomainError as exc:
        raise domain_error_handler(exc) from exc
    await _audit(session, role, "dispute", "order", str(order_id), reason, request)
    return {"status": "disputed"}


@router.get("/partners")
async def admin_partners(
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.OPERATIONS, AdminRole.ADMIN)),
):
    result = await session.execute(select(Partner))
    return [
        {
            "code": p.code,
            "name": p.name,
            "enabled": p.enabled,
            "circuit_breaker_state": p.circuit_breaker_state.value,
            "success_rate": p.success_rate,
        }
        for p in result.scalars().all()
    ]


@router.post("/partners/{partner_code}/enable")
async def enable_partner(
    partner_code: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.OPERATIONS, AdminRole.ADMIN)),
):
    from app.partners.registry import partner_registry

    partner = await partner_registry.enable_partner(session, partner_code)
    await _audit(session, role, "enable_partner", "partner", partner_code, None, request)
    return {"enabled": partner.enabled}


@router.post("/partners/{partner_code}/disable")
async def disable_partner(
    partner_code: str,
    body: AdminDisablePartnerRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.OPERATIONS, AdminRole.ADMIN)),
):
    from app.partners.registry import partner_registry

    partner = await partner_registry.disable_partner(session, partner_code, body.reason)
    await _audit(session, role, "disable_partner", "partner", partner_code, body.reason, request)
    return {"enabled": partner.enabled}


@router.post("/partners/{partner_code}/reset-circuit")
async def reset_circuit(
    partner_code: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.OPERATIONS, AdminRole.ADMIN)),
):
    from app.partners.registry import partner_registry

    partner = await partner_registry.reset_circuit(session, partner_code)
    await _audit(session, role, "reset_circuit", "partner", partner_code, None, request)
    return {"circuit_breaker_state": partner.circuit_breaker_state.value}


@router.get("/webhooks")
async def admin_webhooks(
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.OPERATIONS, AdminRole.ADMIN)),
):
    result = await session.execute(select(WebhookEvent).order_by(WebhookEvent.received_at.desc()).limit(100))
    return [
        {
            "id": str(e.id),
            "partner_code": e.partner_code,
            "event_type": e.event_type,
            "processing_status": e.processing_status.value,
            "signature_valid": e.signature_valid,
        }
        for e in result.scalars().all()
    ]


@router.get("/risk-flags")
async def admin_risk_flags(
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.OPERATIONS, AdminRole.ADMIN)),
):
    result = await session.execute(select(RiskFlag).order_by(RiskFlag.created_at.desc()).limit(100))
    return [{"id": str(f.id), "flag_type": f.flag_type, "severity": f.severity} for f in result.scalars().all()]


@router.get("/ledger/reconciliation")
async def ledger_reconciliation(
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.FINANCE, AdminRole.ADMIN)),
):
    ledger = LedgerService()
    return await ledger.reconcile(session)


@router.post("/emergency-stop")
async def emergency_stop_on(
    request: Request,
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.ADMIN)),
):
    settings = get_settings()
    settings.emergency_stop = True
    EMERGENCY_STOP.set(1)
    await _audit(session, role, "emergency_stop_on", reason="manual", request=request)
    return {"emergency_stop": True}


@router.delete("/emergency-stop")
async def emergency_stop_off(
    request: Request,
    session: AsyncSession = Depends(get_db),
    role: AdminRole = Depends(require_admin(AdminRole.ADMIN)),
):
    settings = get_settings()
    settings.emergency_stop = False
    EMERGENCY_STOP.set(0)
    await _audit(session, role, "emergency_stop_off", request=request)
    return {"emergency_stop": False}
