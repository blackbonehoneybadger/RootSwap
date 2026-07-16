"""Quote Engine: fan out to eligible partners, rank offers, persist quotes."""

import asyncio
import logging
import time
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.assets import validate_route
from app.core.config import get_settings
from app.core.enums import CircuitBreakerState, OrderDirection, QuoteSourceType
from app.core.errors import PartnerUnavailableError, ValidationFailedError
from app.db.base import utcnow
from app.models.partner import Partner
from app.models.quote import Quote
from app.observability.metrics import metrics
from app.partners.base import (
    BasePartnerAdapter,
    CryptoPartnerAdapter,
    FiatPartnerAdapter,
    PartnerError,
    PartnerQuote,
    Route,
)
from app.partners.registry import registry
from app.services import circuit_breaker
from app.services.fees import compute_service_fee, compute_total_fee
from app.services.root_score import compute_root_score

logger = logging.getLogger(__name__)


def allowed_source_types() -> set[QuoteSourceType]:
    settings = get_settings()
    allowed = {QuoteSourceType.REAL}
    if settings.is_production:
        # MOCK/SANDBOX are hard-forbidden in production regardless of flags
        return allowed
    if settings.allow_mock_partners:
        allowed.add(QuoteSourceType.MOCK)
    if settings.allow_sandbox_partners:
        allowed.add(QuoteSourceType.SANDBOX)
    return allowed


async def _fetch_partner_quote(
    adapter: BasePartnerAdapter,
    route: Route,
    amount_in: Decimal,
    timeout: float,
) -> tuple[PartnerQuote | None, float, str | None]:
    """Call one partner. No DB access here — safe to run under asyncio.gather."""
    started = time.monotonic()
    try:
        if isinstance(adapter, FiatPartnerAdapter):
            coro = adapter.get_fiat_quote(route, amount_in)
        elif isinstance(adapter, CryptoPartnerAdapter):
            coro = adapter.get_quote(route, amount_in)
        else:  # pragma: no cover
            return None, 0.0, "unknown adapter type"
        quote = await asyncio.wait_for(coro, timeout=timeout)
        return quote, (time.monotonic() - started) * 1000, None
    except (PartnerError, TimeoutError) as exc:
        return None, (time.monotonic() - started) * 1000, str(exc) or "timeout"


async def create_quotes(
    session: AsyncSession,
    user_id: str,
    direction: OrderDirection,
    from_asset: str,
    from_network: str | None,
    to_asset: str,
    to_network: str | None,
    amount_in: Decimal,
) -> list[dict]:
    settings = get_settings()
    if amount_in <= 0:
        raise ValidationFailedError("amount_in must be positive")
    validate_route(direction, from_asset, from_network, to_asset, to_network, amount_in)

    route = Route(direction, from_asset.upper(), from_network, to_asset.upper(), to_network)
    allowed_sources = allowed_source_types()
    partner_rows = await registry.get_partner_rows(session)

    candidates: list[tuple[BasePartnerAdapter, Partner]] = []
    for adapter in registry.all_adapters():
        row = partner_rows.get(adapter.code)
        if row is None or not row.enabled:
            continue
        if adapter.quote_source_type not in allowed_sources:
            continue
        if not adapter.supports_route(route):
            continue
        circuit_breaker.to_half_open_if_ready(row)
        if not circuit_breaker.can_attempt(row):
            continue
        candidates.append((adapter, row))

    if not candidates:
        raise PartnerUnavailableError("no partners available for this route")

    results = await asyncio.gather(
        *[
            _fetch_partner_quote(
                adapter, route, amount_in, settings.quote_partner_timeout_seconds
            )
            for adapter, _ in candidates
        ]
    )

    partner_quotes: list[tuple[PartnerQuote, Partner]] = []
    for (adapter, row), (pq, latency_ms, error) in zip(candidates, results, strict=True):
        if pq is None:
            await circuit_breaker.record_failure(session, row)
            metrics.inc("partner_quote_failure_total", partner=adapter.code)
            logger.warning(
                "partner quote failed",
                extra={"ctx": {"partner": adapter.code, "error": error}},
            )
            continue
        await circuit_breaker.record_success(session, row, latency_ms)
        if not pq.reserve_available:
            metrics.inc("partner_quote_no_reserve_total", partner=adapter.code)
            continue
        partner_quotes.append((pq, row))
    await session.commit()  # persist circuit breaker/stat updates

    if not partner_quotes:
        raise PartnerUnavailableError("no partner returned a usable quote")

    # service fee is charged in the fiat leg (RUB)
    fiat_amount = (
        amount_in if direction == OrderDirection.BUY
        else max(pq.amount_out for pq, _ in partner_quotes)
    )
    service_fee = compute_service_fee(Decimal(fiat_amount))

    best_amount_out = max(pq.amount_out for pq, _ in partner_quotes)
    totals = [
        compute_total_fee(service_fee, pq.partner_fee, pq.network_fee)
        for pq, _ in partner_quotes
    ]
    lowest_total_fee = min(totals)

    now = utcnow()
    expires_at = now + timedelta(seconds=settings.quote_ttl_seconds)
    enriched = []
    for (pq, row), total_fee in zip(partner_quotes, totals, strict=False):
        # user receives amount_out minus our service fee (converted for BUY)
        if direction == OrderDirection.BUY:
            service_fee_in_out_units = (service_fee / pq.exchange_rate).quantize(
                Decimal("0.00000001")
            )
            final_amount_out = pq.amount_out - service_fee_in_out_units
        else:
            final_amount_out = pq.amount_out - service_fee
        if final_amount_out <= 0:
            continue
        score = compute_root_score(
            amount_out=final_amount_out,
            best_amount_out=best_amount_out,
            total_fee=total_fee,
            lowest_total_fee=lowest_total_fee,
            partner_success_rate=row.success_rate,
            average_latency_ms=row.average_latency_ms,
            reserve_available=pq.reserve_available,
            estimated_time_minutes=pq.estimated_time_minutes,
            kyc_required=pq.kyc_required,
            circuit_state=row.circuit_breaker_state,
        )
        quote = Quote(
            user_id=user_id,
            partner_code=pq.partner_code,
            direction=direction,
            from_asset=route.from_asset,
            from_network=route.from_network,
            to_asset=route.to_asset,
            to_network=route.to_network,
            amount_in=amount_in,
            amount_out=final_amount_out,
            exchange_rate=pq.exchange_rate,
            service_fee=service_fee,
            partner_fee=pq.partner_fee,
            network_fee=pq.network_fee,
            total_fee=total_fee,
            root_score=score,
            quote_source_type=(
                QuoteSourceType.MOCK if row.environment == "mock"
                else QuoteSourceType.SANDBOX if row.environment == "sandbox"
                else QuoteSourceType.REAL
            ),
            expires_at=expires_at,
            raw_partner_response=pq.raw,
        )
        session.add(quote)
        enriched.append(
            {
                "quote": quote,
                "partner_row": row,
                "partner_quote": pq,
                "estimated_time_minutes": pq.estimated_time_minutes,
                "kyc_required": pq.kyc_required,
            }
        )

    if not enriched:
        raise PartnerUnavailableError("no partner returned a usable quote")
    await session.commit()

    # labels: best (highest score), fastest, lowest_fee
    best = max(enriched, key=lambda e: e["quote"].root_score)
    fastest = min(enriched, key=lambda e: e["estimated_time_minutes"])
    lowest = min(enriched, key=lambda e: e["quote"].total_fee)
    for entry in enriched:
        labels = []
        if entry is best:
            labels.append("best")
        if entry is fastest:
            labels.append("fastest")
        if entry is lowest:
            labels.append("lowest_fee")
        entry["labels"] = labels
        logger.info(
            "quote created",
            extra={
                "ctx": {
                    "quote_id": entry["quote"].id,
                    "partner": entry["quote"].partner_code,
                    "direction": direction.value,
                    "source_type": entry["quote"].quote_source_type.value,
                }
            },
        )
    metrics.inc("quotes_created_total", value=float(len(enriched)))
    enriched.sort(key=lambda e: e["quote"].root_score, reverse=True)
    return enriched


_ = CircuitBreakerState  # re-exported for typing convenience in tests
