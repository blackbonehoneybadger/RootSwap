"""Admin API. Every endpoint requires RBAC and writes an AuditLog entry."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminContext, admin_required
from app.api.v1.orders import serialize_order
from app.core.enums import ActorType, AdminRole, OrderStatus
from app.core.errors import NotFoundError, PartnerUnavailableError, ValidationFailedError
from app.db.session import get_db
from app.models.dispute import Dispute
from app.models.order import Order
from app.models.partner import Partner
from app.models.risk_flag import RiskFlag
from app.models.webhook_event import WebhookEvent
from app.partners.base import FiatPartnerAdapter, PartnerError
from app.partners.registry import registry
from app.schemas.api import (
    AdminRefundRequest,
    AdminTransitionRequest,
    DisputeRequest,
    EmergencyStopRequest,
)
from app.services import circuit_breaker, emergency_stop
from app.services import referral as referral_service
from app.services.audit import write_audit
from app.services.ledger import reconcile
from app.services.notifications import notify_order_status
from app.services.order_side_effects import apply_status_side_effects
from app.services.state_machine import transition

router = APIRouter(prefix="/admin", tags=["admin"])

support = admin_required(AdminRole.SUPPORT)
operations = admin_required(AdminRole.OPERATIONS)
finance = admin_required(AdminRole.FINANCE)
admin_only = admin_required(AdminRole.ADMIN)


async def _get_order(session: AsyncSession, order_id: str) -> Order:
    order = (
        await session.execute(select(Order).where(Order.id == order_id))
    ).scalar_one_or_none()
    if order is None:
        raise NotFoundError("order not found")
    return order


@router.get("/orders")
async def admin_list_orders(
    request: Request,
    status: str | None = None,
    ctx: AdminContext = Depends(support),
    session: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Order).order_by(Order.created_at.desc()).limit(200)
    if status:
        query = query.where(Order.status == OrderStatus(status))
    orders = (await session.execute(query)).scalars().all()
    write_audit(
        session, action="admin.orders.list", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return {
        "orders": [
            {
                "id": o.id,
                "status": o.status.value,
                "direction": o.direction.value,
                "partner_code": o.partner_code,
                "amount_in": str(o.amount_in),
                "amount_out": str(o.amount_out),
                "quote_source_type": o.quote_source_type.value,
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ]
    }


@router.get("/orders/{order_id}")
async def admin_get_order(
    order_id: str,
    ctx: AdminContext = Depends(support),
    session: AsyncSession = Depends(get_db),
):
    order = await _get_order(session, order_id)
    write_audit(
        session, action="admin.orders.view", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, entity_type="order", entity_id=order.id,
    )
    await session.commit()
    return await serialize_order(session, order)


@router.post("/orders/{order_id}/transition")
async def admin_transition_order(
    order_id: str,
    body: AdminTransitionRequest,
    ctx: AdminContext = Depends(operations),
    session: AsyncSession = Depends(get_db),
):
    order = await _get_order(session, order_id)
    try:
        target = OrderStatus(body.target_status)
    except ValueError:
        raise ValidationFailedError(f"unknown status {body.target_status}") from None
    previous_status = order.status
    order = await transition(
        session, order, target, ActorType.ADMIN, actor_id=ctx.user.id,
        source="admin_api", message=body.reason,
        expected_version=body.expected_version,
    )
    await apply_status_side_effects(session, order, previous_status)
    write_audit(
        session, action="admin.orders.transition", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, entity_type="order", entity_id=order.id,
        reason=body.reason, metadata={"target": target.value},
    )
    await session.commit()
    return await serialize_order(session, order)


@router.post("/orders/{order_id}/refund")
async def admin_refund_order(
    order_id: str,
    body: AdminRefundRequest,
    ctx: AdminContext = Depends(finance),
    session: AsyncSession = Depends(get_db),
):
    order = await _get_order(session, order_id)
    adapter = registry.get_adapter(order.partner_code)
    if isinstance(adapter, FiatPartnerAdapter) and order.partner_order_id:
        try:
            await adapter.request_refund(order.partner_order_id, body.reason)
        except PartnerError as exc:
            raise PartnerUnavailableError(f"partner refund request failed: {exc}") from exc

    previous_status = order.status
    if order.status in (OrderStatus.COMPLETED, OrderStatus.DISPUTED, OrderStatus.FAILED):
        order = await transition(
            session, order, OrderStatus.REFUND_REQUESTED, ActorType.ADMIN,
            actor_id=ctx.user.id, source="admin_api", message=body.reason,
        )
    order = await transition(
        session, order, OrderStatus.REFUND_PROCESSING, ActorType.ADMIN,
        actor_id=ctx.user.id, source="admin_api", message=body.reason,
    )
    order = await transition(
        session, order, OrderStatus.REFUNDED, ActorType.ADMIN,
        actor_id=ctx.user.id, source="admin_api", message=body.reason,
    )
    await apply_status_side_effects(session, order, previous_status)
    write_audit(
        session, action="admin.orders.refund", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, entity_type="order", entity_id=order.id,
        reason=body.reason,
    )
    await session.commit()
    return await serialize_order(session, order)


@router.post("/orders/{order_id}/dispute")
async def admin_dispute_order(
    order_id: str,
    body: DisputeRequest,
    ctx: AdminContext = Depends(support),
    session: AsyncSession = Depends(get_db),
):
    order = await _get_order(session, order_id)
    order = await transition(
        session, order, OrderStatus.DISPUTED, ActorType.ADMIN,
        actor_id=ctx.user.id, source="admin_api", message=body.reason,
    )
    session.add(Dispute(order_id=order.id, user_id=order.user_id, reason=body.reason))
    await referral_service.freeze_rewards_for_order(session, order.id)
    write_audit(
        session, action="admin.orders.dispute", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, entity_type="order", entity_id=order.id,
        reason=body.reason,
    )
    await session.commit()
    await notify_order_status(session, order)
    return await serialize_order(session, order)


@router.get("/partners")
async def admin_list_partners(
    ctx: AdminContext = Depends(support),
    session: AsyncSession = Depends(get_db),
) -> dict:
    partners = (await session.execute(select(Partner))).scalars().all()
    write_audit(
        session, action="admin.partners.list", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value,
    )
    await session.commit()
    return {
        "partners": [
            {
                "code": p.code,
                "name": p.name,
                "adapter_type": p.adapter_type,
                "enabled": p.enabled,
                "quote_source_type": p.quote_source_type.value,
                "environment": p.environment,
                "circuit_breaker_state": p.circuit_breaker_state.value,
                "consecutive_failures": p.consecutive_failures,
                "success_rate": p.success_rate,
                "average_latency_ms": p.average_latency_ms,
                "disabled_reason": p.disabled_reason,
            }
            for p in partners
        ]
    }


@router.post("/partners/{partner_code}/enable")
async def admin_enable_partner(
    partner_code: str,
    ctx: AdminContext = Depends(operations),
    session: AsyncSession = Depends(get_db),
) -> dict:
    row = await registry.enable_partner(session, partner_code)
    if row is None:
        raise NotFoundError("partner not found")
    write_audit(
        session, action="admin.partners.enable", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, entity_type="partner", entity_id=partner_code,
    )
    await session.commit()
    return {"code": row.code, "enabled": row.enabled}


@router.post("/partners/{partner_code}/disable")
async def admin_disable_partner(
    partner_code: str,
    body: EmergencyStopRequest,
    ctx: AdminContext = Depends(operations),
    session: AsyncSession = Depends(get_db),
) -> dict:
    row = await registry.disable_partner(session, partner_code, body.reason)
    if row is None:
        raise NotFoundError("partner not found")
    write_audit(
        session, action="admin.partners.disable", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, entity_type="partner", entity_id=partner_code,
        reason=body.reason,
    )
    await session.commit()
    return {"code": row.code, "enabled": row.enabled}


@router.post("/partners/{partner_code}/reset-circuit")
async def admin_reset_circuit(
    partner_code: str,
    ctx: AdminContext = Depends(operations),
    session: AsyncSession = Depends(get_db),
) -> dict:
    row = (
        await session.execute(select(Partner).where(Partner.code == partner_code))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("partner not found")
    await circuit_breaker.reset(session, row)
    write_audit(
        session, action="admin.partners.reset_circuit", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, entity_type="partner", entity_id=partner_code,
    )
    await session.commit()
    return {"code": row.code, "circuit_breaker_state": row.circuit_breaker_state.value}


@router.get("/webhooks")
async def admin_list_webhooks(
    ctx: AdminContext = Depends(support),
    session: AsyncSession = Depends(get_db),
) -> dict:
    events = (
        (
            await session.execute(
                select(WebhookEvent).order_by(WebhookEvent.received_at.desc()).limit(200)
            )
        )
        .scalars()
        .all()
    )
    write_audit(
        session, action="admin.webhooks.list", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value,
    )
    await session.commit()
    return {
        "webhooks": [
            {
                "id": e.id,
                "partner_code": e.partner_code,
                "external_event_id": e.external_event_id,
                "event_type": e.event_type,
                "processing_status": e.processing_status.value,
                "processing_attempts": e.processing_attempts,
                "processing_error": e.processing_error,
                "received_at": e.received_at.isoformat(),
            }
            for e in events
        ]
    }


@router.get("/risk-flags")
async def admin_list_risk_flags(
    ctx: AdminContext = Depends(support),
    session: AsyncSession = Depends(get_db),
) -> dict:
    flags = (
        (await session.execute(select(RiskFlag).order_by(RiskFlag.created_at.desc()).limit(200)))
        .scalars()
        .all()
    )
    write_audit(
        session, action="admin.risk_flags.list", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value,
    )
    await session.commit()
    return {
        "risk_flags": [
            {
                "id": f.id,
                "user_id": f.user_id,
                "order_id": f.order_id,
                "flag_type": f.flag_type,
                "severity": f.severity,
                "status": f.status.value,
                "created_at": f.created_at.isoformat(),
            }
            for f in flags
        ]
    }


@router.get("/ledger/reconciliation")
async def admin_ledger_reconciliation(
    ctx: AdminContext = Depends(finance),
    session: AsyncSession = Depends(get_db),
) -> dict:
    result = await reconcile(session)
    write_audit(
        session, action="admin.ledger.reconciliation", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, metadata={"balanced": result["balanced"]},
    )
    await session.commit()
    return result


@router.post("/emergency-stop")
async def admin_emergency_stop(
    body: EmergencyStopRequest,
    ctx: AdminContext = Depends(admin_only),
    session: AsyncSession = Depends(get_db),
) -> dict:
    await emergency_stop.activate(session, set_by=ctx.user.id, reason=body.reason)
    write_audit(
        session, action="admin.emergency_stop.activate", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value, reason=body.reason,
    )
    await session.commit()
    return {"emergency_stop": True}


@router.delete("/emergency-stop")
async def admin_emergency_stop_clear(
    ctx: AdminContext = Depends(admin_only),
    session: AsyncSession = Depends(get_db),
) -> dict:
    await emergency_stop.deactivate(session, set_by=ctx.user.id)
    write_audit(
        session, action="admin.emergency_stop.deactivate", actor_user_id=ctx.user.id,
        actor_role=ctx.role.value,
    )
    await session.commit()
    return {"emergency_stop": False}
