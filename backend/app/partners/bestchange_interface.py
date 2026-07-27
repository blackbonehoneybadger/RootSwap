"""BestChange provider-ready interface — NOT a live adapter.

See docs/integrations/bestchange.md. Do not scrape. Do not invent endpoints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BestChangeRoute:
    from_code: str
    to_code: str


@dataclass(frozen=True)
class BestChangeQuote:
    exchanger_id: str
    exchanger_name: str
    rate: Decimal
    reserve: Decimal | None
    reputation: Decimal | None
    redirect_url: str | None


class BestChangeProvider(ABC):
    """Official-API-only contract. No implementation ships until access exists."""

    @abstractmethod
    async def list_routes(self) -> list[BestChangeRoute]: ...

    @abstractmethod
    async def get_quotes(self, route: BestChangeRoute, amount: Decimal) -> list[BestChangeQuote]: ...

    @abstractmethod
    async def exchanger_metadata(self, exchanger_id: str) -> dict: ...

    @abstractmethod
    async def health_check(self) -> bool: ...


class BestChangeNotConfigured(BestChangeProvider):
    """Placeholder that refuses all calls."""

    async def list_routes(self) -> list[BestChangeRoute]:
        raise RuntimeError("BestChange live integration is not enabled")

    async def get_quotes(self, route: BestChangeRoute, amount: Decimal) -> list[BestChangeQuote]:
        raise RuntimeError("BestChange live integration is not enabled")

    async def exchanger_metadata(self, exchanger_id: str) -> dict:
        raise RuntimeError("BestChange live integration is not enabled")

    async def health_check(self) -> bool:
        return False
