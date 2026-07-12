import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import domain_error_handler, get_current_user
from app.core.exceptions import DomainError
from app.db.session import get_db
from app.models import Dispute, Order, User
from app.schemas import (
    DisputeCreateRequest,
    OrderCreateRequest,
    OrderResponse,
    QuoteCreateRequest,
    QuoteListResponse,
    QuoteResponse,
    ReferralStatsResponse,
    TelegramAuthRequest,
    TokenResponse,
)
from app.security import create_access_token, generate_referral_code, validate_telegram_init_data
from app.services.order_orchestrator import OrderOrchestrator
from app.services.quote_engine import QuoteEngine
from app.services.referral import ReferralService

router = APIRouter(prefix="/api/v1")


def _quote_to_response(quote) -> QuoteResponse:
    raw = quote.raw_partner_response or {}
    return QuoteResponse(
        id=quote.id,
        partner_code=quote.partner_code,
        direction=quote.direction,
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
        root_score=float(quote.root_score),
        quote_source_type=quote.quote_source_type,
        expires_at=quote.expires_at,
        kyc_required=raw.get("kyc_required", False),
        estimated_time_seconds=raw.get("estimated_time_seconds", 600),
    )


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
    return OrderResponse.model_validate(order)


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
    return [OrderResponse.model_validate(o) for o in result.scalars().all()]


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
    return OrderResponse.model_validate(order)


@router.post("/orders/{order_id}/dispute")
async def create_dispute(
    order_id: uuid.UUID,
    body: DisputeCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    dispute = Dispute(order_id=order.id, user_id=user.id, reason=body.reason)
    session.add(dispute)
    return {"status": "dispute_created", "dispute_id": str(dispute.id)}


@router.get("/referral/stats", response_model=ReferralStatsResponse)
async def referral_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReferralService()
    stats = await service.get_stats(session, user)
    return ReferralStatsResponse(**stats)
