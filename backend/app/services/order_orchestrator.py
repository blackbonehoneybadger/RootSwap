"""Order Orchestrator: quote -> order with all invariants enforced.

- valid, owned, unexpired, unconsumed quote
- idempotency key (same key returns the same order)
- one order per quote (DB unique constraint)
- payment instructions / deposit address via partner adapter
- ledger and referral accrual happen only on COMPLETED (webhook/polling layer)
"""

import hashlib
import json
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import ActorType, OrderDirection, OrderStatus, QuoteSourceType
from app.core.errors import (
    ForbiddenError,
    IdempotencyConflictError,
    InvalidTransitionError,
    NotFoundError,
    PartnerUnavailableError,
    QuoteConsumedError,
    QuoteExpiredError,
    ValidationFailedError,
)
from app.db.base import utcnow
from app.models.order import Order
from app.models.payment_instructions import PaymentInstructions
from app.models.quote import Quote
from app.observability.metrics import metrics
from app.partners.base import FiatPartnerAdapter, PartnerError, Route
from app.partners.registry import registry
from app.security.encryption import encrypt_value
from app.security.masking import (
    mask_account,
    mask_card,
    mask_name,
    mask_phone,
    mask_wallet,
)
from app.services import emergency_stop
from app.services.audit import write_audit
from app.services.order_side_effects import apply_status_side_effects
from app.services.state_machine import transition
from app.services.wallet_validation import validate_wallet_address

logger = logging.getLogger(__name__)


def _idempotency_fingerprint(
    quote_id: str,
    wallet_address: str | None,
    payout_details: dict | None,
    payment_method: str | None,
    bank: str | None,
) -> str:
    payload = {
        "quote_id": quote_id,
        "wallet_address": (wallet_address or "").strip(),
        "payout_details": payout_details or {},
        "payment_method": payment_method or "",
        "bank": bank or "",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


async def create_order(
    session: AsyncSession,
    user_id: str,
    quote_id: str,
    idempotency_key: str,
    wallet_address: str | None = None,
    payout_details: dict | None = None,
    payment_method: str | None = None,
    bank: str | None = None,
) -> Order:
    settings = get_settings()
    await emergency_stop.ensure_not_stopped(session)

    if not idempotency_key or len(idempotency_key) > 64:
        raise ValidationFailedError("idempotency_key is required (max 64 chars)")

    fingerprint = _idempotency_fingerprint(
        quote_id, wallet_address, payout_details, payment_method, bank
    )

    # idempotent replay: same user + key + fingerprint -> same order
    existing = (
        await session.execute(
            select(Order).where(
                Order.user_id == user_id, Order.idempotency_key == idempotency_key
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.idempotency_fingerprint and existing.idempotency_fingerprint != fingerprint:
            raise IdempotencyConflictError(
                "idempotency key reused with a different payload"
            )
        return existing

    quote = (
        await session.execute(select(Quote).where(Quote.id == quote_id))
    ).scalar_one_or_none()
    if quote is None:
        raise NotFoundError("quote not found")
    if quote.user_id != user_id:
        raise ForbiddenError("quote belongs to another user")
    if quote.consumed_at is not None:
        raise QuoteConsumedError("quote already consumed")
    if quote.expires_at <= utcnow():
        raise QuoteExpiredError("quote expired")
    if settings.is_production and quote.quote_source_type in (
        QuoteSourceType.MOCK,
        QuoteSourceType.SANDBOX,
    ):
        raise ForbiddenError("mock/sandbox quotes are not allowed in production")

    direction = quote.direction
    if direction == OrderDirection.BUY:
        if not wallet_address:
            raise ValidationFailedError("wallet_address is required for BUY")
        validate_wallet_address(quote.to_asset, quote.to_network, wallet_address)
    else:
        if not payout_details or not payout_details.get("account"):
            raise ValidationFailedError("payout_details are required for SELL")

    adapter = registry.get_adapter(quote.partner_code)
    if adapter is None:
        raise PartnerUnavailableError("partner adapter is not registered")

    route = Route(direction, quote.from_asset, quote.from_network, quote.to_asset, quote.to_network)

    # mark quote consumed before calling the partner (no double-spend of a quote)
    quote.consumed_at = utcnow()
    await session.flush()

    order = Order(
        user_id=user_id,
        quote_id=quote.id,
        partner_code=quote.partner_code,
        direction=direction,
        status=OrderStatus.CREATED,
        from_asset=quote.from_asset,
        from_network=quote.from_network,
        to_asset=quote.to_asset,
        to_network=quote.to_network,
        amount_in=quote.amount_in,
        amount_out=quote.amount_out,
        exchange_rate=quote.exchange_rate,
        service_fee=quote.service_fee,
        partner_fee=quote.partner_fee,
        network_fee=quote.network_fee,
        total_fee=quote.total_fee,
        quote_source_type=quote.quote_source_type,
        idempotency_key=idempotency_key,
        idempotency_fingerprint=fingerprint,
    )
    if wallet_address:
        order.wallet_address_encrypted = encrypt_value(wallet_address)
        order.wallet_address_masked = mask_wallet(wallet_address)
    if payout_details:
        order.payout_details_encrypted = encrypt_value(json.dumps(payout_details))
        order.payout_details_masked = mask_account(str(payout_details.get("account", "")))
    session.add(order)
    try:
        await session.flush()
    except IntegrityError:
        # A concurrent request won the (user_id, idempotency_key) or (quote_id)
        # unique constraint. Roll back, then reconcile against the winner —
        # NEVER return an order that belongs to a different payload.
        await session.rollback()
        replay = (
            await session.execute(
                select(Order).where(
                    Order.user_id == user_id, Order.idempotency_key == idempotency_key
                )
            )
        ).scalar_one_or_none()
        if replay is not None:
            if (
                replay.idempotency_fingerprint
                and replay.idempotency_fingerprint != fingerprint
            ):
                metrics.inc("order_idempotency_conflict_total")
                raise IdempotencyConflictError(
                    "idempotency key reused with a different payload"
                ) from None
            return replay
        # No order for that key -> the conflict was the per-quote unique
        # constraint: a different active order already holds this quote.
        raise QuoteConsumedError("an active order already exists for this quote") from None

    await transition(session, order, OrderStatus.QUOTE_CONFIRMED, ActorType.USER, user_id)

    try:
        if isinstance(adapter, FiatPartnerAdapter):
            result = await adapter.create_fiat_order(
                route,
                quote.amount_in,
                client_order_id=order.id,
                payment_method=payment_method,
                bank=bank,
                payout_details=payout_details,
                wallet_address=wallet_address,
            )
        else:
            result = await adapter.create_order(
                route, quote.amount_in, client_order_id=order.id, wallet_address=wallet_address
            )
    except PartnerError as exc:
        await transition(
            session, order, OrderStatus.CANCELLED, ActorType.SYSTEM,
            message=f"partner order creation failed: {exc}",
        )
        await session.commit()
        metrics.inc("order_partner_create_failed_total", partner=quote.partner_code)
        raise PartnerUnavailableError("partner failed to create order, please retry") from exc

    # The external partner order now exists. Any failure past this point would
    # orphan it, so wrap all remaining local persistence in a compensation
    # (saga) boundary: on error, roll back locally, best-effort cancel the
    # remote order, record an audit trail + metric, and surface the error —
    # never return a "successful" order backed by an orphaned remote order.
    partner_order_id = result.partner_order_id
    try:
        order.partner_order_id = partner_order_id

        if result.payment_instructions:
            instructions = _build_payment_instructions(order, result.payment_instructions)
            session.add(instructions)
            await session.flush()
            order.payment_instructions_id = instructions.id
        if result.deposit_address:
            order.wallet_address_encrypted = encrypt_value(result.deposit_address)
            order.wallet_address_masked = mask_wallet(result.deposit_address)

        await transition(session, order, OrderStatus.AWAITING_PAYMENT, ActorType.SYSTEM)
        await session.commit()
    except Exception as exc:
        await _compensate_remote_order(
            session, adapter, quote.partner_code, partner_order_id, exc
        )
        raise PartnerUnavailableError(
            "order could not be finalized; the reservation was cancelled, please retry"
        ) from exc
    metrics.inc("orders_created_total", direction=direction.value)
    logger.info(
        "order created",
        extra={
            "ctx": {
                "order_id": order.id,
                "partner": order.partner_code,
                "direction": direction.value,
                "source_type": order.quote_source_type.value,
            }
        },
    )
    return order


async def _compensate_remote_order(
    session: AsyncSession,
    adapter,
    partner_code: str,
    partner_order_id: str,
    error: Exception,
) -> None:
    """Best-effort saga compensation for an orphaned remote partner order.

    Called when the remote order was created but local persistence failed. Rolls
    back the local transaction, cancels the remote order best-effort, and records
    a safe audit trail + metric. If the cancel itself fails, a distinct metric
    fires and a recovery AuditLog is written so a future retry worker (TODO:
    durable partner_compensation_tasks queue) can reconcile it. No sensitive data
    is logged (only the exception class name). The original error is re-raised by
    the caller.
    """
    safe_error = type(error).__name__  # class name only — never the message
    await session.rollback()
    metrics.inc("order_partner_compensation_total", partner=partner_code)
    logger.error(
        "compensating orphaned remote partner order",
        extra={"ctx": {"partner": partner_code, "partner_order_id": partner_order_id}},
    )
    cancelled = False
    try:
        cancelled = await adapter.cancel_order(partner_order_id)
    except PartnerError:
        cancelled = False
    if cancelled:
        write_audit(
            session,
            action="order.partner_compensation.cancelled",
            actor_role=ActorType.SYSTEM.value,
            entity_type="partner_order",
            entity_id=partner_order_id,
            reason=safe_error,
            metadata={"partner_code": partner_code},
        )
    else:
        metrics.inc("order_partner_compensation_failed_total", partner=partner_code)
        write_audit(
            session,
            action="order.partner_compensation.cancel_failed",
            actor_role=ActorType.SYSTEM.value,
            entity_type="partner_order",
            entity_id=partner_order_id,
            reason=f"remote order requires manual reconciliation: {safe_error}",
            metadata={"partner_code": partner_code, "needs_recovery": True},
        )
    await session.commit()


def _build_payment_instructions(order: Order, raw: dict) -> PaymentInstructions:
    settings = get_settings()
    expires_at = utcnow() + timedelta(seconds=settings.payment_instructions_ttl_seconds)

    def enc(key: str) -> str | None:
        value = raw.get(key)
        return encrypt_value(str(value)) if value else None

    return PaymentInstructions(
        order_id=order.id,
        partner_order_id=order.partner_order_id,
        payment_method=raw.get("payment_method", "SBP"),
        bank_name=raw.get("bank_name"),
        recipient_name_encrypted=enc("recipient_name"),
        account_number_encrypted=enc("account_number"),
        card_number_encrypted=enc("card_number"),
        sbp_phone_encrypted=enc("sbp_phone"),
        masked_recipient_name=mask_name(raw["recipient_name"]) if raw.get("recipient_name") else None,
        masked_account=mask_account(raw["account_number"]) if raw.get("account_number") else None,
        masked_card=mask_card(raw["card_number"]) if raw.get("card_number") else None,
        masked_phone=mask_phone(raw["sbp_phone"]) if raw.get("sbp_phone") else None,
        amount=order.amount_in,
        currency=raw.get("currency", "RUB"),
        payment_comment=raw.get("payment_comment"),
        expires_at=expires_at,
    )


async def get_payment_instructions_if_valid(
    session: AsyncSession, order: Order
) -> PaymentInstructions | None:
    if not order.payment_instructions_id:
        return None
    instructions = (
        await session.execute(
            select(PaymentInstructions).where(
                PaymentInstructions.id == order.payment_instructions_id
            )
        )
    ).scalar_one_or_none()
    if instructions is None or instructions.deleted_at is not None:
        return None
    if instructions.viewed_at is None:
        instructions.viewed_at = utcnow()
        await session.flush()
    return instructions


CANCELLABLE_STATUSES = frozenset(
    {OrderStatus.CREATED, OrderStatus.QUOTE_CONFIRMED, OrderStatus.AWAITING_PAYMENT}
)


async def cancel_user_order(
    session: AsyncSession, order: Order, user_id: str
) -> Order:
    if order.user_id != user_id:
        raise ForbiddenError("order belongs to another user")
    if order.status not in CANCELLABLE_STATUSES:
        raise InvalidTransitionError(
            f"order in status {order.status.value} cannot be cancelled by user"
        )

    if order.partner_order_id:
        adapter = registry.get_adapter(order.partner_code)
        if adapter is not None:
            try:
                await adapter.cancel_order(order.partner_order_id)
            except PartnerError:
                logger.warning(
                    "partner cancel failed",
                    extra={"ctx": {"order_id": order.id, "partner": order.partner_code}},
                )

    order = await transition(
        session,
        order,
        OrderStatus.CANCELLED,
        ActorType.USER,
        actor_id=user_id,
        message="cancelled by user",
    )
    await session.commit()
    metrics.inc("orders_cancelled_total", direction=order.direction.value)
    return order


async def expire_stale_awaiting_orders(session: AsyncSession) -> int:
    """Expire AWAITING_PAYMENT orders whose payment instructions have expired."""
    now = utcnow()
    orders = (
        (
            await session.execute(
                select(Order).where(Order.status == OrderStatus.AWAITING_PAYMENT)
            )
        )
        .scalars()
        .all()
    )
    expired = 0
    for order in orders:
        if not order.payment_instructions_id:
            continue
        instructions = (
            await session.execute(
                select(PaymentInstructions).where(
                    PaymentInstructions.id == order.payment_instructions_id
                )
            )
        ).scalar_one_or_none()
        if instructions and instructions.expires_at <= now:
            previous_status = order.status
            await transition(
                session, order, OrderStatus.EXPIRED, ActorType.SYSTEM,
                message="payment window expired",
            )
            instructions.deleted_at = now
            await apply_status_side_effects(session, order, previous_status)
            expired += 1
    if expired:
        await session.commit()
    return expired
