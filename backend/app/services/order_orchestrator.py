"""Order Orchestrator: quote -> order with all invariants enforced.

- valid, owned, unexpired, unconsumed quote
- idempotency key (same key returns the same order)
- one order per quote (DB unique constraint)
- payment instructions / deposit address via partner adapter
- ledger and referral accrual happen only on COMPLETED (webhook/polling layer)
"""

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
from app.services.order_side_effects import apply_status_side_effects
from app.services.state_machine import transition
from app.services.wallet_validation import validate_wallet_address

logger = logging.getLogger(__name__)


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

    # idempotent replay: same user + key -> same order
    existing = (
        await session.execute(
            select(Order).where(
                Order.user_id == user_id, Order.idempotency_key == idempotency_key
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
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
        await session.rollback()
        replay = (
            await session.execute(
                select(Order).where(
                    Order.user_id == user_id, Order.idempotency_key == idempotency_key
                )
            )
        ).scalar_one_or_none()
        if replay is not None:
            return replay
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

    order.partner_order_id = result.partner_order_id

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
