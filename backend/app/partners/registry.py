"""PartnerRegistry — the single entry point to partner adapters.

Adapter instances live in memory; operational state (enabled, circuit breaker,
stats) lives in the `partners` table and is synced via `sync_partner_rows`.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CircuitBreakerState, QuoteSourceType
from app.db.base import utcnow
from app.models.partner import Partner
from app.partners.base import BasePartnerAdapter, Route


class PartnerRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BasePartnerAdapter] = {}

    def register_adapter(self, adapter: BasePartnerAdapter) -> None:
        self._adapters[adapter.code] = adapter

    def get_adapter(self, code: str) -> BasePartnerAdapter | None:
        return self._adapters.get(code)

    def all_adapters(self) -> list[BasePartnerAdapter]:
        return list(self._adapters.values())

    def get_supported_routes(self) -> dict[str, list[Route]]:
        return {code: a.supported_routes() for code, a in self._adapters.items()}

    def filter_by_environment(
        self, adapters: list[BasePartnerAdapter], environments: set[str]
    ) -> list[BasePartnerAdapter]:
        return [a for a in adapters if a.environment in environments]

    def filter_by_quote_source_type(
        self, adapters: list[BasePartnerAdapter], allowed: set[QuoteSourceType]
    ) -> list[BasePartnerAdapter]:
        return [a for a in adapters if a.quote_source_type in allowed]

    @staticmethod
    def filter_by_circuit_breaker(
        rows: dict[str, Partner], adapters: list[BasePartnerAdapter], now: datetime | None = None
    ) -> list[BasePartnerAdapter]:
        """Exclude partners whose circuit is OPEN and still cooling down."""
        now = now or utcnow()
        result = []
        for adapter in adapters:
            row = rows.get(adapter.code)
            if row is None:
                continue
            if row.circuit_breaker_state == CircuitBreakerState.OPEN:
                if row.cooldown_until is None or row.cooldown_until > now:
                    continue
            result.append(adapter)
        return result

    async def get_partner_rows(self, session: AsyncSession) -> dict[str, Partner]:
        rows = (await session.execute(select(Partner))).scalars().all()
        return {r.code: r for r in rows}

    async def get_enabled_adapters(self, session: AsyncSession) -> list[BasePartnerAdapter]:
        rows = await self.get_partner_rows(session)
        return [
            a
            for a in self._adapters.values()
            if a.code in rows and rows[a.code].enabled
        ]

    async def sync_partner_rows(self, session: AsyncSession) -> None:
        """Ensure a partners row exists for every registered adapter."""
        rows = await self.get_partner_rows(session)
        for adapter in self._adapters.values():
            if adapter.code not in rows:
                session.add(
                    Partner(
                        code=adapter.code,
                        name=adapter.name,
                        adapter_type=adapter.adapter_type,
                        enabled=True,
                        quote_source_type=adapter.quote_source_type,
                        environment=adapter.environment,
                    )
                )
        await session.commit()

    async def enable_partner(self, session: AsyncSession, code: str) -> Partner | None:
        row = (
            await session.execute(select(Partner).where(Partner.code == code))
        ).scalar_one_or_none()
        if row:
            row.enabled = True
            row.disabled_reason = None
            await session.commit()
        return row

    async def disable_partner(
        self, session: AsyncSession, code: str, reason: str | None = None
    ) -> Partner | None:
        row = (
            await session.execute(select(Partner).where(Partner.code == code))
        ).scalar_one_or_none()
        if row:
            row.enabled = False
            row.disabled_reason = reason
            await session.commit()
        return row


registry = PartnerRegistry()
