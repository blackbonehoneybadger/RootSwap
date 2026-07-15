import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import domain_error_handler, get_current_user
from app.core.config import get_settings
from app.core.datetime_utils import ensure_aware, utcnow
from app.core.enums import ActorType, OrderStatus, QuoteSourceType
from app.core.exceptions import DomainError, ValidationError
from app.db.session import get_db
from app.models import Dispute, Order, PaymentInstructions, User
from app.partners.registry import partner_registry
from app.schemas import (
    DisputeCreateRequest,
    OrderCreateRequest,
    OrderResponse,
    PaymentInstructionsResponse,
    QuoteCreateRequest,
    QuoteListResponse,
    QuoteResponse,
    ReferralStatsResponse,
    TelegramAuthRequest,
    TokenResponse,
)
from app.security import (
    create_access_token,
    decrypt_value,
    generate_referral_code,
    validate_telegram_init_data,
)
from app.services.order_orchestrator import OrderOrchestrator
from app.services.quote_engine import QuoteEngine
from app.services.referral import ReferralService

router = APIRouter(prefix="/api/v1")


class DevAuthRequest(BaseModel):
    telegram_id: int = Field(default=900001, gt=0)
    username: str | None = "dev_user"
    first_name: str | None = "Dev"
    referral_code: str | None = None


def ensure_aware_pi_expired(pi: PaymentInstructions) -> bool:
    return ensure_aware(pi.expires_at) < utcnow()


def _quote_to_response(quote) -> QuoteResponse:
    from app.core.money import q8

    raw = quote.raw_partner_response or {}
    return QuoteResponse(
        id=quote.id,
        partner_code=quote.partner_code,
        direction=quote.direction,
        from_asset=quote.from_asset,
        from_network=quote.from_network,
        to_asset=quote.to_asset,
        to_network=quote.to_network,
        amount_in=q8(quote.amount_in),
        amount_out=q8(quote.amount_out),
        exchange_rate=q8(quote.exchange_rate),
        service_fee=q8(quote.service_fee),
        partner_fee=q8(quote.partner_fee),
        network_fee=q8(quote.network_fee),
        total_fee=q8(quote.total_fee),
        root_score=float(quote.root_score),
        quote_source_type=quote.quote_source_type,
        expires_at=quote.expires_at,
        kyc_required=raw.get("kyc_required", False),
        estimated_time_seconds=raw.get("estimated_time_seconds", 600),
    )


def _dec(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return decrypt_value(raw)
    except Exception:
        return None


def _pi_to_response(
    pi: PaymentInstructions, source: QuoteSourceType
) -> PaymentInstructionsResponse:
    from app.core.money import q8

    reveal = source in (QuoteSourceType.MOCK, QuoteSourceType.SANDBOX)
    return PaymentInstructionsResponse(
        id=pi.id,
        payment_method=pi.payment_method,
        bank_name=pi.bank_name,
        masked_recipient_name=pi.masked_recipient_name,
        masked_account=pi.masked_account,
        masked_card=pi.masked_card,
        masked_phone=pi.masked_phone,
        deposit_address_masked=pi.deposit_address_masked,
        amount=q8(pi.amount),
        currency=pi.currency,
        payment_comment=pi.payment_comment,
        expires_at=pi.expires_at,
        recipient_name=_dec(pi.recipient_name_encrypted) if reveal else None,
        account_number=_dec(pi.account_number_encrypted) if reveal else None,
        card_number=_dec(pi.card_number_encrypted) if reveal else None,
        sbp_phone=_dec(pi.sbp_phone_encrypted) if reveal else None,
        deposit_address=_dec(pi.deposit_address_encrypted) if reveal else None,
    )


def _order_to_response(order: Order) -> OrderResponse:
    data = OrderResponse.model_validate(order)
    if order.payment_instructions is not None:
        data.payment_instructions = _pi_to_response(
            order.payment_instructions, order.quote_source_type
        )
    return data


@router.post("/auth/telegram", response_model=TokenResponse)
async def auth_telegram(body: TelegramAuthRequest, session: AsyncSession = Depends(get_db)):
    try:
        parsed = validate_telegram_init_data(body.init_data)
    except DomainError as exc:
        raise domain_error_handler(exc) from exc
    user_data = parsed.get("user", {})
    telegram_id = int(user_data.get("id", 0))
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Invalid user data")

    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    referral_service = ReferralService()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=user_data.get("username"),
            first_name=user_data.get("first_name"),
            referral_code=generate_referral_code(),
        )
        session.add(user)
        await session.flush()
        ref_code = body.referral_code
        if ref_code and ref_code.startswith("ref_"):
            ref_code = ref_code[4:]
        try:
            await referral_service.attach_referrer(session, user, ref_code)
        except DomainError as exc:
            raise domain_error_handler(exc) from exc
    else:
        user.username = user_data.get("username") or user.username
        user.first_name = user_data.get("first_name") or user.first_name

    token = create_access_token(str(user.id), {"telegram_id": telegram_id})
    return TokenResponse(access_token=token, user_id=user.id)


def _require_dev_endpoints() -> None:
    """Hard gate: ENABLE_DEV_ENDPOINTS must be on and environment != production."""
    if not get_settings().dev_endpoints_allowed:
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/assets")
async def list_assets():
    """Public list of supported / planned assets (honest MVP surface)."""
    from app.core.assets import ASSETS, SUPPORTED_ROUTES

    return {
        "assets": [
            {
                "symbol": a.symbol,
                "name": a.name,
                "network": a.network,
                "decimals": a.decimals,
                "enabled": a.enabled,
                "min_amount": a.min_amount,
                "max_amount": a.max_amount,
                "status": a.status,
            }
            for a in ASSETS.values()
        ],
        "routes": [
            {
                "direction": d.value,
                "from_asset": fa,
                "from_network": fn,
                "to_asset": ta,
                "to_network": tn,
            }
            for d, fa, fn, ta, tn in SUPPORTED_ROUTES
        ],
    }


@router.post("/auth/dev", response_model=TokenResponse)
async def auth_dev(body: DevAuthRequest, session: AsyncSession = Depends(get_db)):
    """Browser DEV auth when Telegram initData is unavailable (development only)."""
    _require_dev_endpoints()
    result = await session.execute(select(User).where(User.telegram_id == body.telegram_id))
    user = result.scalar_one_or_none()
    referral_service = ReferralService()
    if not user:
        user = User(
            telegram_id=body.telegram_id,
            username=body.username,
            first_name=body.first_name,
            referral_code=generate_referral_code(),
        )
        session.add(user)
        await session.flush()
        try:
            await referral_service.attach_referrer(session, user, body.referral_code)
        except DomainError:
            pass
    token = create_access_token(
        str(user.id),
        {"telegram_id": body.telegram_id, "auth_mode": "dev"},
    )
    return TokenResponse(access_token=token, user_id=user.id)


@router.post("/quotes", response_model=QuoteListResponse)
async def create_quote(
    body: QuoteCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    engine = QuoteEngine()
    try:
        result = await engine.create_quotes(
            session,
            user,
            body.direction,
            body.from_asset.upper(),
            body.from_network,
            body.to_asset.upper(),
            body.to_network,
            body.amount_in,
            body.payment_method,
            body.bank_name,
            body.scenario,
        )
    except DomainError as exc:
        raise domain_error_handler(exc) from exc
    return QuoteListResponse(
        best=_quote_to_response(result["best"]) if result["best"] else None,
        fastest=_quote_to_response(result["fastest"]) if result["fastest"] else None,
        lowest_fee=_quote_to_response(result["lowest_fee"]) if result["lowest_fee"] else None,
        all=[_quote_to_response(q) for q in result["all"]],
    )


@router.post("/orders", response_model=OrderResponse)
async def create_order(
    body: OrderCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    orchestrator = OrderOrchestrator()
    try:
        order = await orchestrator.create_order(
            session,
            user,
            body.quote_id,
            body.idempotency_key,
            body.wallet_address,
            body.payout_details,
            body.payment_method,
            body.bank_name,
            body.scenario,
        )
        result = await session.execute(
            select(Order)
            .where(Order.id == order.id)
            .options(selectinload(Order.payment_instructions))
        )
        order = result.scalar_one()
    except DomainError as exc:
        raise domain_error_handler(exc) from exc
    return _order_to_response(order)


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user.id)
        .options(selectinload(Order.payment_instructions))
        .order_by(Order.created_at.desc())
    )
    return [_order_to_response(o) for o in result.scalars().all()]


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .options(selectinload(Order.payment_instructions))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_response(order)


@router.post("/orders/{order_id}/simulate-payment", response_model=OrderResponse)
async def simulate_payment(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """DEMO only: advance MOCK/SANDBOX order to COMPLETED as if payment succeeded."""
    _require_dev_endpoints()

    result = await session.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .options(selectinload(Order.payment_instructions))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.quote_source_type not in (QuoteSourceType.MOCK, QuoteSourceType.SANDBOX):
        raise HTTPException(status_code=400, detail="simulate-payment only for MOCK/SANDBOX")
    if order.status != OrderStatus.AWAITING_PAYMENT:
        raise HTTPException(status_code=400, detail="Order is not awaiting payment")
    if order.payment_instructions and ensure_aware_pi_expired(order.payment_instructions):
        raise HTTPException(status_code=400, detail="Payment instructions expired")

    if order.partner_order_id:
        adapter = partner_registry.get_adapter(order.partner_code)
        if adapter and hasattr(adapter, "simulate_status"):
            adapter.simulate_status(order.partner_order_id, "completed")

    orchestrator = OrderOrchestrator()
    try:
        # SYSTEM actor — USER cannot jump to COMPLETED via state machine ACL.
        order = await orchestrator.advance_to(
            session,
            order,
            OrderStatus.COMPLETED,
            ActorType.SYSTEM,
            f"dev:{user.id}",
            {"source": "simulate_payment"},
        )
    except DomainError as exc:
        raise domain_error_handler(exc) from exc

    result = await session.execute(
        select(Order)
        .where(Order.id == order.id)
        .options(selectinload(Order.payment_instructions))
    )
    return _order_to_response(result.scalar_one())


@router.post("/orders/{order_id}/dispute")
async def create_dispute(
    order_id: uuid.UUID,
    body: DisputeCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .options(selectinload(Order.payment_instructions))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status in (
        OrderStatus.CREATED,
        OrderStatus.QUOTE_CONFIRMED,
        OrderStatus.AWAITING_PAYMENT,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
        OrderStatus.FAILED,
    ):
        raise domain_error_handler(
            ValidationError("Dispute is only available after payment is detected")
        )

    orchestrator = OrderOrchestrator()
    referral = ReferralService()
    try:
        if order.status != OrderStatus.DISPUTED:
            order = await orchestrator.transition(
                session,
                order,
                OrderStatus.DISPUTED,
                ActorType.USER,
                str(user.id),
                {"reason": body.reason},
            )
            await referral.freeze_on_dispute(session, order)
    except DomainError as exc:
        raise domain_error_handler(exc) from exc

    dispute = Dispute(order_id=order.id, user_id=user.id, reason=body.reason)
    session.add(dispute)
    return {
        "status": "dispute_created",
        "dispute_id": str(dispute.id),
        "order_status": order.status.value,
    }


@router.get("/referral/stats", response_model=ReferralStatsResponse)
async def referral_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReferralService()
    stats = await service.get_stats(session, user)
    return ReferralStatsResponse(**stats)
