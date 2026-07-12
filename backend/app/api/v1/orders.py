from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.enums import ActorType, OrderDirection, OrderStatus, QuoteSourceType
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models.dispute import Dispute
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.models.user import User
from app.schemas.api import (
    CreateOrderRequest,
    DisputeRequest,
    OrderEventOut,
    OrderOut,
    OrdersResponse,
    PaymentInstructionsOut,
)
from app.security.encryption import decrypt_value
from app.services import referral as referral_service
from app.services.audit import write_audit
from app.services.notifications import notify_order_status
from app.services.order_orchestrator import (
    cancel_user_order,
    create_order,
    get_payment_instructions_if_valid,
)
from app.services.state_machine import transition

router = APIRouter(prefix="/orders", tags=["orders"])


def _payment_instructions_out(
    instructions,
    quote_source_type: QuoteSourceType,
) -> PaymentInstructionsOut:
    reveal = quote_source_type in (QuoteSourceType.MOCK, QuoteSourceType.SANDBOX)

    def dec(field: str) -> str | None:
        raw = getattr(instructions, f"{field}_encrypted", None)
        if not raw:
            return None
        return decrypt_value(raw)

    return PaymentInstructionsOut(
        payment_method=instructions.payment_method,
        bank_name=instructions.bank_name,
        masked_recipient_name=instructions.masked_recipient_name,
        masked_account=instructions.masked_account,
        masked_card=instructions.masked_card,
        masked_phone=instructions.masked_phone,
        amount=str(instructions.amount),
        currency=instructions.currency,
        payment_comment=instructions.payment_comment,
        expires_at=instructions.expires_at.isoformat(),
        recipient_name=dec("recipient_name") if reveal else None,
        account_number=dec("account_number") if reveal else None,
        card_number=dec("card_number") if reveal else None,
        sbp_phone=dec("sbp_phone") if reveal else None,
    )


async def serialize_order(session: AsyncSession, order: Order) -> OrderOut:
    events = (
        (
            await session.execute(
                select(OrderEvent)
                .where(OrderEvent.order_id == order.id)
                .order_by(OrderEvent.created_at.asc(), OrderEvent.id.asc())
            )
        )
        .scalars()
        .all()
    )
    instructions = await get_payment_instructions_if_valid(session, order)
    instructions_out = None
    if instructions is not None:
        instructions_out = _payment_instructions_out(instructions, order.quote_source_type)
    deposit_address = None
    deposit_network = None
    if order.direction == OrderDirection.SELL and order.wallet_address_encrypted:
        # partner-provided deposit address: the user must see it in full to pay
        deposit_address = decrypt_value(order.wallet_address_encrypted)
        deposit_network = order.from_network
    return OrderOut(
        id=order.id,
        status=order.status.value,
        direction=order.direction,
        from_asset=order.from_asset,
        from_network=order.from_network,
        to_asset=order.to_asset,
        to_network=order.to_network,
        amount_in=str(order.amount_in),
        amount_out=str(order.amount_out),
        exchange_rate=str(order.exchange_rate),
        service_fee=str(order.service_fee),
        partner_fee=str(order.partner_fee),
        network_fee=str(order.network_fee),
        total_fee=str(order.total_fee),
        quote_source_type=order.quote_source_type.value,
        wallet_address_masked=order.wallet_address_masked,
        payout_details_masked=order.payout_details_masked,
        deposit_address=deposit_address,
        deposit_network=deposit_network,
        payment_instructions=instructions_out,
        events=[
            OrderEventOut(
                status=e.status.value, message=e.message, created_at=e.created_at.isoformat()
            )
            for e in events
        ],
        created_at=order.created_at.isoformat(),
    )


@router.post("", response_model=OrderOut)
async def post_order(
    body: CreateOrderRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await create_order(
        session,
        user_id=user.id,
        quote_id=body.quote_id,
        idempotency_key=body.idempotency_key,
        wallet_address=body.wallet_address,
        payout_details=body.payout_details.model_dump() if body.payout_details else None,
        payment_method=body.payment_method,
        bank=body.bank,
    )
    await notify_order_status(session, order)
    return await serialize_order(session, order)


@router.get("", response_model=OrdersResponse)
async def list_orders(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrdersResponse:
    orders = (
        (
            await session.execute(
                select(Order)
                .where(Order.user_id == user.id)
                .order_by(Order.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    result = OrdersResponse(orders=[await serialize_order(session, o) for o in orders])
    await session.commit()
    return result


async def _get_owned_order(session: AsyncSession, user: User, order_id: str) -> Order:
    order = (
        await session.execute(
            select(Order).where(Order.id == order_id, Order.user_id == user.id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise NotFoundError("order not found")
    return order


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await _get_owned_order(session, user, order_id)
    result = await serialize_order(session, order)
    await session.commit()
    return result


@router.post("/{order_id}/dispute", response_model=OrderOut)
async def dispute_order(
    order_id: str,
    body: DisputeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await _get_owned_order(session, user, order_id)
    order = await transition(
        session, order, OrderStatus.DISPUTED, ActorType.USER, actor_id=user.id,
        message=f"dispute opened: {body.reason[:100]}",
    )
    session.add(
        Dispute(order_id=order.id, user_id=user.id, reason=body.reason)
    )
    await referral_service.freeze_rewards_for_order(session, order.id)
    write_audit(
        session, action="order.dispute.opened", actor_user_id=user.id,
        entity_type="order", entity_id=order.id, reason=body.reason,
    )
    await session.commit()
    await notify_order_status(session, order)
    return await serialize_order(session, order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await _get_owned_order(session, user, order_id)
    order = await cancel_user_order(session, order, user.id)
    await notify_order_status(session, order)
    return await serialize_order(session, order)
