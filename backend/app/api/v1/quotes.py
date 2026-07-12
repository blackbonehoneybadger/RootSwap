from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.partners.registry import registry
from app.schemas.api import QuoteOut, QuoteRequest, QuotesResponse
from app.services import emergency_stop
from app.services.quote_engine import create_quotes

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post("", response_model=QuotesResponse)
async def post_quotes(
    body: QuoteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> QuotesResponse:
    await emergency_stop.ensure_not_stopped(session)
    enriched = await create_quotes(
        session,
        user_id=user.id,
        direction=body.direction,
        from_asset=body.from_asset,
        from_network=body.from_network,
        to_asset=body.to_asset,
        to_network=body.to_network,
        amount_in=body.amount_in,
    )
    quotes = []
    for entry in enriched:
        quote = entry["quote"]
        adapter = registry.get_adapter(quote.partner_code)
        quotes.append(
            QuoteOut(
                quote_id=quote.id,
                partner_code=quote.partner_code,
                partner_name=adapter.name if adapter else quote.partner_code,
                direction=quote.direction,
                from_asset=quote.from_asset,
                from_network=quote.from_network,
                to_asset=quote.to_asset,
                to_network=quote.to_network,
                amount_in=str(quote.amount_in),
                amount_out=str(quote.amount_out),
                exchange_rate=str(quote.exchange_rate),
                service_fee=str(quote.service_fee),
                partner_fee=str(quote.partner_fee),
                network_fee=str(quote.network_fee),
                total_fee=str(quote.total_fee),
                root_score=str(quote.root_score),
                quote_source_type=quote.quote_source_type.value,
                expires_at=quote.expires_at.isoformat(),
                kyc_required=entry["kyc_required"],
                estimated_time_minutes=entry["estimated_time_minutes"],
                labels=entry["labels"],
            )
        )
    return QuotesResponse(quotes=quotes)
