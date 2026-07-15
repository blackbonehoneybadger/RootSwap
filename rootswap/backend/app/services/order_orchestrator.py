import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.datetime_utils import ensure_aware, utcnow
from app.core.enums import ActorType, OrderDirection, OrderStatus
from app.core.exceptions import (
    ConflictError,
    EmergencyStopError,
    ForbiddenError,
    InvalidTransitionError,
    NotFoundError,
    ValidationError,
)
from app.models import AuditLog, Order, OrderEvent, PaymentInstructions, Quote, User
from app.observability.logging import get_logger
from app.partners.base import FiatPartnerAdapter, OrderRequest
from app.partners.registry import partner_registry
from app.security import encrypt_value, mask_string, validate_wallet_address
from app.services.ledger import LedgerService
from app.services.referral import ReferralService
from app.services.state_machine import OrderStateMachine

logger = get_logger(__name__)


class OrderOrchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.state_machine = OrderStateMachine()
        self.ledger = LedgerService()
        self.referral = ReferralService()

    async def create_order(
        self,
        session: AsyncSession,
        user: User,
        quote_id: uuid.UUID,
        idempotency_key: str,
        wallet_address: str | None = None,
        payout_details: dict | None = None,
        payment_method: str | None = None,
        bank_name: str | None = None,
        scenario: str | None = None,
    ) -> Order:
        if self.settings.emergency_stop:
            raise EmergencyStopError()

        existing = await session.execute(
            select(Order).where(Order.idempotency_key == idempotency_key)
        )
        existing_order = existing.scalar_one_or_none()
        if existing_order:
            return existing_order

        result = await session.execute(select(Quote).where(Quote.id == quote_id))
        quote = result.scalar_one_or_none()
        if not quote:
            raise NotFoundError("Quote not found")
        if quote.user_id != user.id:
            raise ForbiddenError("Quote does not belong to user")
        if ensure_aware(quote.expires_at) < utcnow():
            raise ValidationError("Quote expired")
        if quote.consumed_at:
            raise ConflictError("Quote already consumed")

        active = await session.execute(
            select(Order).where(
                Order.quote_id == quote_id,
                Order.status.notin_(
                    [
                        OrderStatus.COMPLETED,
                        OrderStatus.FAILED,
                        OrderStatus.EXPIRED,
                        OrderStatus.CANCELLED,
                        OrderStatus.REFUNDED,
                    ]
                ),
            )
        )
        if active.scalar_one_or_none():
            raise ConflictError("Active order already exists for this quote")

        if quote.direction == OrderDirection.BUY:
            if not wallet_address or not wallet_address.strip():
                raise ValidationError("wallet_address is required for BUY orders")
            validate_wallet_address(quote.to_asset, quote.to_network, wallet_address)
        elif quote.direction == OrderDirection.SELL:
            if not payout_details or not payout_details.get("account"):
                raise ValidationError("payout_details.account is required for SELL orders")

        quote.consumed_at = utcnow()

        adapter = partner_registry.get_adapter(quote.partner_code)
        if not isinstance(adapter, FiatPartnerAdapter):
            raise ValidationError("Unsupported partner adapter")

        if scenario and hasattr(adapter, "set_scenario"):
            adapter.set_scenario(scenario)

        order = Order(
            id=uuid.uuid4(),
            user_id=user.id,
            quote_id=quote.id,
            partner_code=quote.partner_code,
            direction=quote.direction,
            status=OrderStatus.CREATED,
            from_asset=quote.from_asset,
            from_network=quote.from_network,
            to_asset=quote.to_asset,
            to_network=quote.to_network,
            amount_in=float(quote.amount_in),
            amount_out=float(quote.amount_out),
            exchange_rate=float(quote.exchange_rate),
            service_fee=float(quote.service_fee),
            partner_fee=float(quote.partner_fee),
            network_fee=float(quote.network_fee),
            total_fee=float(quote.total_fee),
            quote_source_type=quote.quote_source_type,
            idempotency_key=idempotency_key,
            wallet_address_encrypted=encrypt_value(wallet_address) if wallet_address else None,
            wallet_address_masked=mask_string(wallet_address) if wallet_address else None,
            payout_details_encrypted=encrypt_value(str(payout_details)) if payout_details else None,
            payout_details_masked="***" if payout_details else None,
            version=1,
        )
        session.add(order)
        await session.flush()

        await self._add_event(session, order, OrderStatus.CREATED, ActorType.USER, str(user.id))
        await self.transition(
            session, order, OrderStatus.QUOTE_CONFIRMED, ActorType.SYSTEM, None, {}
        )

        partner_request = OrderRequest(
            quote_id=str(quote.id),
            partner_quote_ref=None,
            wallet_address=wallet_address,
            payout_details=payout_details,
            payment_method=payment_method,
            bank_name=bank_name,
            idempotency_key=idempotency_key,
            amount_in=float(quote.amount_in),
            scenario=scenario,
        )
        try:
            partner_result = await adapter.create_fiat_order(partner_request)
        except Exception as exc:
            await self.transition(
                session, order, OrderStatus.FAILED, ActorType.SYSTEM, None,
                {"error": str(exc)},
            )
            await session.flush()
            raise ValidationError(f"Partner failed to create order: {exc}") from exc
        order.partner_order_id = partner_result.partner_order_id
        if hasattr(adapter, "set_scenario"):
            adapter.set_scenario(None)

        await self.transition(
            session, order, OrderStatus.AWAITING_PAYMENT, ActorType.SYSTEM, None, {}
        )

        instructions = await adapter.get_payment_instructions(partner_result.partner_order_id)
        settings = get_settings()
        expires_at = instructions.expires_at
        if ensure_aware(expires_at) > utcnow() + timedelta(seconds=settings.payment_instructions_ttl_seconds):
            expires_at = utcnow() + timedelta(seconds=settings.payment_instructions_ttl_seconds)
        pi = PaymentInstructions(
            id=uuid.uuid4(),
            order_id=order.id,
            partner_order_id=partner_result.partner_order_id,
            payment_method=instructions.payment_method or payment_method or "SBP",
            bank_name=instructions.bank_name or bank_name,
            recipient_name_encrypted=encrypt_value(instructions.recipient_name or ""),
            account_number_encrypted=encrypt_value(instructions.account_number or ""),
            card_number_encrypted=encrypt_value(instructions.card_number or ""),
            sbp_phone_encrypted=encrypt_value(instructions.sbp_phone or ""),
            masked_recipient_name=mask_string(instructions.recipient_name or "", 2, 2),
            masked_account=mask_string(instructions.account_number or "", 4, 4),
            masked_card=mask_string(instructions.card_number or "", 4, 4),
            masked_phone=mask_string(instructions.sbp_phone or "", 3, 2),
            deposit_address_encrypted=encrypt_value(instructions.deposit_address or "")
            if instructions.deposit_address
            else None,
            deposit_address_masked=mask_string(instructions.deposit_address or "")
            if instructions.deposit_address
            else None,
            amount=float(instructions.amount or quote.amount_in),
            currency=instructions.currency,
            payment_comment=instructions.payment_comment,
            expires_at=expires_at,
        )
        # Flush order is critical for PostgreSQL (non-deferrable FKs):
        # 1) INSERT payment_instructions with order_id (order already exists)
        # 2) UPDATE orders.payment_instructions_id (soft pointer, no FK)
        session.add(pi)
        await session.flush()
        order.payment_instructions_id = pi.id
        order.expired_at = expires_at
        await session.flush()
        return order

    async def advance_to(
        self,
        session: AsyncSession,
        order: Order,
        target: OrderStatus,
        actor: ActorType,
        actor_id: str | None,
        metadata: dict | None = None,
    ) -> Order:
        """Walk intermediate happy-path statuses when partner jumps ahead."""
        metadata = metadata or {}
        if order.status == target:
            return order
        chain = self.state_machine.get_chain(order.direction)
        if order.status not in chain or target not in chain:
            return await self.transition(session, order, target, actor, actor_id, metadata)
        cur_idx = chain.index(order.status)
        tgt_idx = chain.index(target)
        if tgt_idx <= cur_idx:
            raise InvalidTransitionError(
                f"Cannot move backwards from {order.status.value} to {target.value}"
            )
        for status in chain[cur_idx + 1 : tgt_idx + 1]:
            order = await self.transition(session, order, status, actor, actor_id, metadata)
        return order

    async def transition(
        self,
        session: AsyncSession,
        order: Order,
        target: OrderStatus,
        actor: ActorType,
        actor_id: str | None,
        metadata: dict,
        expected_version: int | None = None,
        audit: AuditLog | None = None,
    ) -> Order:
        try:
            self.state_machine.validate_transition(
                order.status, target, actor, order.version, expected_version
            )
        except Exception as exc:
            session.add(
                AuditLog(
                    action="order_transition_denied",
                    entity_type="order",
                    entity_id=str(order.id),
                    reason=str(exc),
                    metadata_={"from": order.status.value, "to": target.value},
                )
            )
            raise

        order.status = target
        order.version += 1
        if target == OrderStatus.COMPLETED:
            order.completed_at = utcnow()
            await self.ledger.post_completed_order(session, order)
            await self.referral.process_completed_order(session, order)

        await self._add_event(session, order, target, actor, actor_id, metadata)
        await session.flush()
        return order

    async def _add_event(
        self,
        session: AsyncSession,
        order: Order,
        status: OrderStatus,
        actor: ActorType,
        actor_id: str | None,
        payload: dict | None = None,
    ) -> None:
        session.add(
            OrderEvent(
                order_id=order.id,
                status=status,
                message=f"Order transitioned to {status.value}",
                actor_type=actor.value,
                actor_id=actor_id,
                payload=payload,
            )
        )
