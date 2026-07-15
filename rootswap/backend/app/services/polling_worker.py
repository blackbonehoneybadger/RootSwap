import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import FINAL_ORDER_STATUSES, ActorType, OrderStatus
from app.db.session import async_session_factory
from app.models import Order
from app.observability.logging import get_logger
from app.partners.base import FiatPartnerAdapter
from app.partners.mock_fiat import PARTNER_STATUS_MAP
from app.partners.registry import partner_registry
from app.services.order_orchestrator import OrderOrchestrator

logger = get_logger(__name__)


class PollingWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.orchestrator = OrderOrchestrator()
        self._running = False

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.poll_once()
            except Exception as exc:
                logger.error("polling_error", error=str(exc))
            await asyncio.sleep(self.settings.polling_interval_seconds)

    def stop(self) -> None:
        self._running = False

    async def poll_once(self) -> None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Order).where(Order.status.notin_(list(FINAL_ORDER_STATUSES)))
            )
            orders = list(result.scalars().all())
            for order in orders:
                await self._poll_order(session, order)
            await session.commit()

    async def _poll_order(self, session: AsyncSession, order: Order) -> None:
        if not order.partner_order_id:
            return
        adapter = partner_registry.get_adapter(order.partner_code)
        if not isinstance(adapter, FiatPartnerAdapter):
            return
        try:
            status_result = await adapter.get_order_status(order.partner_order_id)
        except Exception as exc:
            logger.warning("poll_partner_error", order_id=str(order.id), error=str(exc))
            return
        internal = PARTNER_STATUS_MAP.get(status_result.status)
        if not internal or internal == order.status:
            return
        try:
            happy = {
                OrderStatus.PAYMENT_DETECTED,
                OrderStatus.PAYMENT_CONFIRMING,
                OrderStatus.PROCESSING,
                OrderStatus.PAYOUT_SENT,
                OrderStatus.COMPLETED,
            }
            if internal in happy:
                await self.orchestrator.advance_to(
                    session,
                    order,
                    internal,
                    ActorType.SYSTEM,
                    "polling_worker",
                    status_result.raw_response,
                )
            else:
                await self.orchestrator.transition(
                    session,
                    order,
                    internal,
                    ActorType.SYSTEM,
                    "polling_worker",
                    status_result.raw_response,
                )
        except Exception as exc:
            logger.warning(
                "poll_transition_skipped",
                order_id=str(order.id),
                error=str(exc),
            )
