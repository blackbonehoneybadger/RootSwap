import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActorType, OrderStatus, WebhookProcessingStatus
from app.core.exceptions import NotFoundError
from app.models import Order, WebhookEvent
from app.observability.logging import get_logger
from app.observability.metrics import WEBHOOK_EVENTS
from app.partners.mock_fiat import PARTNER_STATUS_MAP
from app.partners.registry import partner_registry
from app.security import hash_payload
from app.services.order_orchestrator import OrderOrchestrator
from app.services.referral import ReferralService

logger = get_logger(__name__)


class WebhookService:
    def __init__(self) -> None:
        self.orchestrator = OrderOrchestrator()
        self.referral = ReferralService()

    async def process_webhook(
        self,
        session: AsyncSession,
        partner_code: str,
        payload: bytes,
        headers: dict[str, str],
    ) -> dict:
        adapter = partner_registry.get_adapter(partner_code)
        valid, data = await adapter.verify_webhook(payload, headers)

        payload_dict = data if data else {}
        if not valid:
            WEBHOOK_EVENTS.labels(partner=partner_code, status="invalid_signature").inc()
            event = WebhookEvent(
                partner_code=partner_code,
                external_event_id=payload_dict.get("event_id", str(uuid.uuid4())),
                partner_order_id=payload_dict.get("partner_order_id"),
                event_type=payload_dict.get("status", "unknown"),
                payload_hash=hash_payload(payload_dict or {"raw": payload.decode(errors="ignore")[:100]}),
                raw_payload={"invalid": True},
                signature_valid=False,
                processing_status=WebhookProcessingStatus.FAILED,
                processing_error="Invalid signature",
            )
            session.add(event)
            return {"status": "rejected", "reason": "invalid_signature"}

        external_event_id = data.get("event_id", hash_payload(data))
        existing = await session.execute(
            select(WebhookEvent).where(
                WebhookEvent.partner_code == partner_code,
                WebhookEvent.external_event_id == external_event_id,
            )
        )
        if existing.scalar_one_or_none():
            WEBHOOK_EVENTS.labels(partner=partner_code, status="duplicate").inc()
            return {"status": "duplicate"}

        event = WebhookEvent(
            partner_code=partner_code,
            external_event_id=external_event_id,
            partner_order_id=data.get("partner_order_id"),
            event_type=data.get("status", "unknown"),
            payload_hash=hash_payload(data),
            raw_payload=data,
            signature_valid=True,
            processing_status=WebhookProcessingStatus.PROCESSING,
        )
        session.add(event)
        await session.flush()

        try:
            await self._apply_status(session, partner_code, data)
            event.processing_status = WebhookProcessingStatus.PROCESSED
            event.processed_at = datetime.now(UTC)
            WEBHOOK_EVENTS.labels(partner=partner_code, status="processed").inc()
        except Exception as exc:
            event.processing_status = WebhookProcessingStatus.FAILED
            event.processing_error = str(exc)
            event.processing_attempts += 1
            WEBHOOK_EVENTS.labels(partner=partner_code, status="failed").inc()
            raise

        return {"status": "processed"}

    async def _apply_status(self, session: AsyncSession, partner_code: str, data: dict) -> None:
        partner_order_id = data.get("partner_order_id")
        if not partner_order_id:
            return
        result = await session.execute(
            select(Order).where(Order.partner_order_id == partner_order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order not found for webhook")

        partner_status = data.get("status", "")
        internal_status = PARTNER_STATUS_MAP.get(partner_status)
        if not internal_status:
            return

        if order.status == internal_status:
            return

        if internal_status == OrderStatus.DISPUTED:
            await self.referral.freeze_on_dispute(session, order)

        await self.orchestrator.transition(
            session, order, internal_status, ActorType.PARTNER, partner_code, data
        )
