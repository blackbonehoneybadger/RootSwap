
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CircuitBreakerState, QuoteSourceType
from app.core.exceptions import NotFoundError
from app.models import Partner
from app.partners.base import CryptoPartnerAdapter, FiatPartnerAdapter
from app.partners.mock_fiat import SUPPORTED_ROUTES, MockFiatPartnerAdapter


class PartnerRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, FiatPartnerAdapter | CryptoPartnerAdapter] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_adapter(MockFiatPartnerAdapter())
        self.register_adapter(MockFiatPartnerAdapter(partner_code="mock_fiat_backup"))

    def register_adapter(self, adapter: FiatPartnerAdapter | CryptoPartnerAdapter) -> None:
        self._adapters[adapter.partner_code] = adapter

    def get_adapter(self, partner_code: str) -> FiatPartnerAdapter | CryptoPartnerAdapter:
        adapter = self._adapters.get(partner_code)
        if not adapter:
            raise NotFoundError(f"Partner adapter not found: {partner_code}")
        return adapter

    def get_enabled_adapters(
        self,
        db_partners: list[Partner] | None = None,
    ) -> list[FiatPartnerAdapter | CryptoPartnerAdapter]:
        if not db_partners:
            return list(self._adapters.values())
        enabled_codes = {p.code for p in db_partners if p.enabled}
        return [a for code, a in self._adapters.items() if code in enabled_codes]

    def get_supported_routes(self) -> dict:
        return {d.value: routes for d, routes in SUPPORTED_ROUTES.items()}

    def filter_by_environment(
        self, adapters: list, environment: str, db_partners: list[Partner]
    ) -> list:
        env_map = {p.code: p.environment for p in db_partners}
        return [a for a in adapters if env_map.get(a.partner_code, "sandbox") == environment]

    def filter_by_quote_source_type(
        self, adapters: list, source_type: QuoteSourceType, db_partners: list[Partner]
    ) -> list:
        type_map = {p.code: p.quote_source_type for p in db_partners}
        return [a for a in adapters if type_map.get(a.partner_code) == source_type]

    def filter_by_circuit_breaker(self, adapters: list, db_partners: list[Partner]) -> list:
        cb_map = {p.code: p.circuit_breaker_state for p in db_partners}
        return [
            a
            for a in adapters
            if cb_map.get(a.partner_code, CircuitBreakerState.CLOSED) != CircuitBreakerState.OPEN
        ]

    async def enable_partner(self, session: AsyncSession, partner_code: str) -> Partner:
        partner = await self._get_partner(session, partner_code)
        partner.enabled = True
        partner.disabled_reason = None
        return partner

    async def disable_partner(
        self, session: AsyncSession, partner_code: str, reason: str | None = None
    ) -> Partner:
        partner = await self._get_partner(session, partner_code)
        partner.enabled = False
        partner.disabled_reason = reason
        return partner

    async def _get_partner(self, session: AsyncSession, partner_code: str) -> Partner:
        result = await session.execute(select(Partner).where(Partner.code == partner_code))
        partner = result.scalar_one_or_none()
        if not partner:
            raise NotFoundError(f"Partner not found: {partner_code}")
        return partner

    async def reset_circuit(self, session: AsyncSession, partner_code: str) -> Partner:
        partner = await self._get_partner(session, partner_code)
        partner.circuit_breaker_state = CircuitBreakerState.CLOSED
        partner.consecutive_failures = 0
        partner.circuit_opened_at = None
        partner.cooldown_until = None
        return partner


partner_registry = PartnerRegistry()
