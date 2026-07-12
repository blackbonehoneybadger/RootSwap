"""Partner webhook subsystem.

Guarantees: signature + timestamp verification, replay protection, dedup by
(partner_code, external_event_id), idempotent processing, no duplicate ledger
postings or referral rewards, retry counter with dead-letter state.
"""

import hashlib
import json
import logging
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import (
    ActorType,
    OrderStatus,
    WebhookProcessingStatus,
)
from app.core.errors import InvalidTransitionError, UnknownWebhookEventError, WebhookRejectedError
from app.db.base import utcnow
from app.models.order import Order
from app.models.webhook_event import WebhookEvent
from app.observability.metrics import metrics
from app.partners.registry import registry
from app.security.masking import mask_mapping
from app.services.order_side_effects import apply_status_side_effects
from app.services.state_machine import advance_along_happy_path, transition

logger = logging.getLogger(__name__)

# partner event_type -> internal order status
EVENT_STATUS_MAP = {
    "payment_detected": OrderStatus.PAYMENT_DETECTED,
    "payment_confirming": OrderStatus.PAYMENT_CONFIRMING,
    "processing": OrderStatus.PROCESSING,
    "payout_sent": OrderStatus.PAYOUT_SENT,
    "completed": OrderStatus.COMPLETED,
    "expired": OrderStatus.EXPIRED,
    "failed": OrderStatus.FAILED,
    "cancelled": OrderStatus.CANCELLED,
    "refund_processing": OrderStatus.REFUND_PROCESSING,
    "refunded": OrderStatus.REFUNDED,
    "refund_failed": OrderStatus.REFUND_FAILED,
}


async def ingest_webhook(
    session: AsyncSession,
    partner_code: str,
    raw_body: bytes,
    signature: str,
    timestamp: str,
) -> WebhookEvent:
    settings = get_settings()
    adapter = registry.get_adapter(partner_code)
    if adapter is None:
        metrics.inc("webhook_rejected_total", reason="unknown_partner")
        raise WebhookRejectedError("unknown partner")

    # timestamp freshness (replay window)
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        metrics.inc("webhook_rejected_total", reason="bad_timestamp")
        raise WebhookRejectedError("missing or malformed timestamp") from None
    if abs(time.time() - ts) > settings.webhook_timestamp_tolerance_seconds:
        metrics.inc("webhook_rejected_total", reason="stale_timestamp")
        raise WebhookRejectedError("timestamp outside tolerance window (replay?)")

    signature_valid = adapter.verify_webhook(raw_body, signature or "", timestamp)
    if not signature_valid:
        metrics.inc("webhook_rejected_total", reason="bad_signature")
        raise WebhookRejectedError("invalid signature")

    try:
        payload = json.loads(raw_body.decode())
    except (ValueError, UnicodeDecodeError):
        metrics.inc("webhook_rejected_total", reason="bad_payload")
        raise WebhookRejectedError("payload is not valid JSON") from None

    external_event_id = str(payload.get("event_id") or "")
    event_type = str(payload.get("event_type") or "")
    partner_order_id = payload.get("partner_order_id")
    if not external_event_id or not event_type:
        metrics.inc("webhook_rejected_total", reason="missing_fields")
        raise WebhookRejectedError("event_id and event_type are required")

    payload_hash = hashlib.sha256(raw_body).hexdigest()

    # dedup by (partner_code, external_event_id)
    existing = (
        await session.execute(
            select(WebhookEvent).where(
                WebhookEvent.partner_code == partner_code,
                WebhookEvent.external_event_id == external_event_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        metrics.inc("webhook_duplicate_total", partner=partner_code)
        if existing.processing_status != WebhookProcessingStatus.PROCESSED:
            return await _process_event(session, existing)
        return existing

    event = WebhookEvent(
        partner_code=partner_code,
        external_event_id=external_event_id,
        partner_order_id=str(partner_order_id) if partner_order_id else None,
        event_type=event_type,
        payload_hash=payload_hash,
        raw_payload=mask_mapping(payload),
        signature_valid=True,
    )
    session.add(event)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        dup = (
            await session.execute(
                select(WebhookEvent).where(
                    WebhookEvent.partner_code == partner_code,
                    WebhookEvent.external_event_id == external_event_id,
                )
            )
        ).scalar_one()
        metrics.inc("webhook_duplicate_total", partner=partner_code)
        return dup

    metrics.inc("webhook_received_total", partner=partner_code)
    return await _process_event(session, event)


async def _process_event(session: AsyncSession, event: WebhookEvent) -> WebhookEvent:
    settings = get_settings()
    event.processing_attempts += 1
    try:
        await _apply_event(session, event)
        event.processing_status = WebhookProcessingStatus.PROCESSED
        event.processed_at = utcnow()
        event.processing_error = None
        metrics.inc("webhook_processed_total", partner=event.partner_code)
    except InvalidTransitionError as exc:
        # e.g. duplicate 'completed' on an already-final order: safe no-op
        event.processing_status = WebhookProcessingStatus.PROCESSED
        event.processed_at = utcnow()
        event.processing_error = f"noop: {exc.message}"
        metrics.inc("webhook_noop_total", partner=event.partner_code)
    except UnknownWebhookEventError as exc:
        event.processing_status = WebhookProcessingStatus.DEAD_LETTER
        event.processed_at = utcnow()
        event.processing_error = str(exc.message)[:500]
        metrics.inc("webhook_dead_letter_total", partner=event.partner_code, reason="unknown_event")
    except Exception as exc:  # unexpected: keep for retry / dead-letter
        if event.processing_attempts >= settings.webhook_max_processing_attempts:
            event.processing_status = WebhookProcessingStatus.DEAD_LETTER
            metrics.inc("webhook_dead_letter_total", partner=event.partner_code)
        else:
            event.processing_status = WebhookProcessingStatus.RETRYING
            metrics.inc("webhook_retrying_total", partner=event.partner_code)
        event.processing_error = str(exc)[:500]
        logger.exception("webhook processing failed")
    await session.commit()
    return event


async def _apply_event(session: AsyncSession, event: WebhookEvent) -> None:
    target = EVENT_STATUS_MAP.get(event.event_type)
    if target is None:
        raise UnknownWebhookEventError(f"unknown event type {event.event_type}")
    if not event.partner_order_id:
        raise InvalidTransitionError("event has no partner_order_id")

    order = (
        await session.execute(
            select(Order).where(
                Order.partner_code == event.partner_code,
                Order.partner_order_id == event.partner_order_id,
            )
        )
    ).scalar_one_or_none()
    if order is None:
        raise ValueError(f"order for partner_order_id {event.partner_order_id} not found")

    if order.status == target:
        return  # idempotent replay of the same status

    previous_status = order.status
    if target in (
        OrderStatus.PAYMENT_DETECTED,
        OrderStatus.PAYMENT_CONFIRMING,
        OrderStatus.PROCESSING,
        OrderStatus.PAYOUT_SENT,
        OrderStatus.COMPLETED,
    ):
        order = await advance_along_happy_path(
            session, order, target, ActorType.PARTNER,
            actor_id=event.partner_code, source="webhook",
            message=f"partner event {event.event_type}",
        )
    else:
        if target == OrderStatus.REFUND_PROCESSING and order.status == OrderStatus.COMPLETED:
            order = await transition(
                session, order, OrderStatus.REFUND_REQUESTED, ActorType.PARTNER,
                actor_id=event.partner_code, source="webhook",
            )
        order = await transition(
            session, order, target, ActorType.PARTNER,
            actor_id=event.partner_code, source="webhook",
            message=f"partner event {event.event_type}",
        )

    await apply_status_side_effects(session, order, previous_status)


async def retry_pending_events(session: AsyncSession) -> int:
    """Retry queue: re-process RETRYING events (called by the background worker)."""
    events = (
        (
            await session.execute(
                select(WebhookEvent).where(
                    WebhookEvent.processing_status == WebhookProcessingStatus.RETRYING
                )
            )
        )
        .scalars()
        .all()
    )
    for event in events:
        await _process_event(session, event)
    return len(events)
