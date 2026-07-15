import asyncio
import time
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.assets import validate_route
from app.core.config import get_settings
from app.core.datetime_utils import ensure_aware, utcnow
from app.core.enums import CircuitBreakerState, OrderDirection, QuoteSourceType
from app.core.exceptions import ForbiddenError, ValidationError
from app.models import Partner, Quote, User
from app.observability.logging import get_logger
from app.partners.base import FiatPartnerAdapter, QuoteRequest
from app.partners.registry import partner_registry
from app.security import mask_sensitive_data
from app.services.circuit_breaker import CircuitBreakerService
from app.services.fees import calculate_fees, calculate_root_score, classify_quotes

logger = get_logger(__name__)


class QuoteEngine:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.circuit_breaker = CircuitBreakerService()

    async def _get_partners(self, session: AsyncSession) -> list[Partner]:
        result = await session.execute(select(Partner).where(Partner.enabled.is_(True)))
        return list(result.scalars().all())

    def _validate_source_type(self, source_type: QuoteSourceType) -> None:
        if self.settings.environment == "production" and source_type in (
            QuoteSourceType.MOCK,
            QuoteSourceType.SANDBOX,
        ):
            raise ForbiddenError("MOCK/SANDBOX quotes are forbidden in production")

    async def create_quotes(
        self,
        session: AsyncSession,
        user: User,
        direction: OrderDirection,
        from_asset: str,
        from_network: str | None,
        to_asset: str,
        to_network: str | None,
        amount_in: float,
        payment_method: str | None = None,
        bank_name: str | None = None,
        scenario: str | None = None,
    ) -> dict:
        validate_route(direction, from_asset, from_network, to_asset, to_network, amount_in)

        db_partners = await self._get_partners(session)
        if not db_partners:
            raise ValidationError("No partners available")

        adapters = partner_registry.get_enabled_adapters(db_partners)
        adapters = partner_registry.filter_by_circuit_breaker(adapters, db_partners)

        quotes: list[Quote] = []

        async def fetch_quote(adapter: FiatPartnerAdapter, partner: Partner) -> Quote | None:
            await self.circuit_breaker.maybe_half_open(session, partner)
            if not isinstance(adapter, FiatPartnerAdapter):
                return None
            if hasattr(adapter, "supports_route") and not adapter.supports_route(
                direction, from_asset, from_network, to_asset, to_network
            ):
                return None
            if partner.circuit_breaker_state == CircuitBreakerState.OPEN:
                if partner.cooldown_until and utcnow() < ensure_aware(partner.cooldown_until):
                    return None

            self._validate_source_type(partner.quote_source_type)
            if scenario and hasattr(adapter, "set_scenario"):
                adapter.set_scenario(scenario)

            request = QuoteRequest(
                direction=direction.value,
                from_asset=from_asset,
                from_network=from_network,
                to_asset=to_asset,
                to_network=to_network,
                amount_in=amount_in,
                payment_method=payment_method,
                bank_name=bank_name,
                scenario=scenario,
            )
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    adapter.get_fiat_quote(request),
                    timeout=self.settings.partner_quote_timeout_seconds,
                )
                latency = (time.monotonic() - start) * 1000
                await self.circuit_breaker.record_success(session, partner, latency)
            except Exception as exc:
                await self.circuit_breaker.record_failure(session, partner)
                logger.warning(
                    "quote_partner_failed",
                    extra={"partner": partner.code, "error": str(exc), "masked": True},
                )
                return None
            finally:
                if hasattr(adapter, "set_scenario"):
                    adapter.set_scenario(None)

            service_fee, total_fee = calculate_fees(
                amount_in, result.partner_fee, result.network_fee, self.settings.service_fee_rate
            )
            root_score = calculate_root_score(
                result.amount_out,
                partner.success_rate,
                partner.average_latency_ms,
                result.reserve_available,
                total_fee,
                result.estimated_time_seconds,
                result.kyc_required,
                partner.circuit_breaker_state,
            )
            expires_at = utcnow() + timedelta(seconds=self.settings.quote_ttl_seconds)
            raw = {
                **result.raw_response,
                "estimated_time_seconds": result.estimated_time_seconds,
                "kyc_required": result.kyc_required,
            }
            quote = Quote(
                id=uuid.uuid4(),
                user_id=user.id,
                partner_code=partner.code,
                direction=direction,
                from_asset=from_asset,
                from_network=from_network,
                to_asset=to_asset,
                to_network=to_network,
                amount_in=amount_in,
                amount_out=result.amount_out,
                exchange_rate=result.exchange_rate,
                service_fee=service_fee,
                partner_fee=result.partner_fee,
                network_fee=result.network_fee,
                total_fee=total_fee,
                root_score=root_score,
                quote_source_type=partner.quote_source_type,
                expires_at=expires_at,
                raw_partner_response=raw,
            )
            session.add(quote)
            logger.info(
                "quote_created",
                extra=mask_sensitive_data(
                    {
                        "quote_id": str(quote.id),
                        "partner": partner.code,
                        "amount_in": amount_in,
                        "amount_out": result.amount_out,
                        "source_type": partner.quote_source_type.value,
                    }
                ),
            )
            return quote

        tasks = []
        partner_map = {p.code: p for p in db_partners}
        for adapter in adapters:
            partner = partner_map.get(adapter.partner_code)
            if partner:
                tasks.append(fetch_quote(adapter, partner))

        results = await asyncio.gather(*tasks)
        quotes = [q for q in results if q is not None]
        await session.flush()
        return classify_quotes(quotes)
