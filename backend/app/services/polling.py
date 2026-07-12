"""Polling fallback: when webhooks are missing, ask partners for order status.

Runs as a background task. Stops touching orders once they reach a final status.
Status changes flow through the same state machine as webhooks; ledger/referral
side effects are triggered exactly once thanks to idempotent posting keys.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.enums import FINAL_ORDER_STATUSES, ActorType, OrderStatus
from app.core.errors import InvalidTransitionError
from app.models.order import Order
from app.observability.metrics import metrics
from app.partners.base import PartnerError
from app.partners.registry import registry
from app.services.order_orchestrator import expire_stale_awaiting_orders
from app.services.order_side_effects import apply_status_side_effects
from app.services.state_machine import advance_along_happy_path, transition
from app.services.webhook_processor import EVENT_STATUS_MAP, retry_pending_events

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = [s for s in OrderStatus if s not in FINAL_ORDER_STATUSES]


async def poll_active_orders_once(session: AsyncSession) -> int:
    """One polling pass. Returns the number of orders whose status changed."""
    changed = 0
    orders = (
        (
            await session.execute(
                select(Order).where(Order.status.in_(ACTIVE_STATUSES))
            )
        )
        .scalars()
        .all()
    )
    for order in orders:
        if not order.partner_order_id:
            continue
        adapter = registry.get_adapter(order.partner_code)
        if adapter is None:
            continue
        try:
            partner_status = await adapter.get_order_status(order.partner_order_id)
        except PartnerError:
            metrics.inc("polling_partner_error_total", partner=order.partner_code)
            continue
        target = EVENT_STATUS_MAP.get(partner_status)
        if target is None or target == order.status:
            continue
        previous = order.status
        try:
            if target in (
                OrderStatus.PAYMENT_DETECTED,
                OrderStatus.PAYMENT_CONFIRMING,
                OrderStatus.PROCESSING,
                OrderStatus.PAYOUT_SENT,
                OrderStatus.COMPLETED,
            ):
                order = await advance_along_happy_path(
                    session, order, target, ActorType.SYSTEM, source="polling",
                    message=f"polling detected partner status {partner_status}",
                )
            else:
                order = await transition(
                    session, order, target, ActorType.SYSTEM, source="polling",
                    message=f"polling detected partner status {partner_status}",
                )
        except InvalidTransitionError:
            continue
        await apply_status_side_effects(session, order, previous)
        await session.commit()
        changed += 1
        metrics.inc("polling_status_change_total")
    return changed


async def run_polling_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    settings = get_settings()
    logger.info("polling fallback worker started")
    while True:
        try:
            async with session_factory() as session:
                await expire_stale_awaiting_orders(session)
                await poll_active_orders_once(session)
                await retry_pending_events(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("polling pass failed")
        await asyncio.sleep(settings.polling_interval_seconds)
