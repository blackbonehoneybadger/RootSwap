"""Partner adapter contracts.

Business logic must never instantiate adapters directly — always go through
PartnerRegistry. Adapters are stateless facades over partner APIs (mock/sandbox/real).
"""

import abc
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.enums import OrderDirection, QuoteSourceType


class PartnerError(Exception):
    """Any partner-side failure (network, rejection, invalid response)."""


@dataclass(frozen=True)
class Route:
    direction: OrderDirection
    from_asset: str
    from_network: str | None
    to_asset: str
    to_network: str | None


@dataclass
class PartnerQuote:
    partner_code: str
    direction: OrderDirection
    from_asset: str
    from_network: str | None
    to_asset: str
    to_network: str | None
    amount_in: Decimal
    amount_out: Decimal
    exchange_rate: Decimal
    partner_fee: Decimal
    network_fee: Decimal
    estimated_time_minutes: int
    kyc_required: bool
    reserve_available: bool
    raw: dict = field(default_factory=dict)


@dataclass
class PartnerOrderResult:
    partner_order_id: str
    status: str
    payment_instructions: dict | None = None
    deposit_address: str | None = None
    deposit_network: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class PartnerLimits:
    min_amount: Decimal
    max_amount: Decimal
    currency: str


class BasePartnerAdapter(abc.ABC):
    code: str
    name: str
    adapter_type: str  # "fiat" | "crypto"
    quote_source_type: QuoteSourceType
    environment: str  # mock | sandbox | production

    @abc.abstractmethod
    def supported_routes(self) -> list[Route]: ...

    @abc.abstractmethod
    def verify_webhook(self, payload: bytes, signature: str, timestamp: str) -> bool: ...

    @abc.abstractmethod
    async def health_check(self) -> bool: ...

    def supports_route(self, route: Route) -> bool:
        return route in self.supported_routes()


class FiatPartnerAdapter(BasePartnerAdapter):
    adapter_type = "fiat"

    @abc.abstractmethod
    async def get_fiat_quote(self, route: Route, amount_in: Decimal) -> PartnerQuote: ...

    @abc.abstractmethod
    async def create_fiat_order(
        self,
        route: Route,
        amount_in: Decimal,
        client_order_id: str,
        payment_method: str | None = None,
        bank: str | None = None,
        payout_details: dict | None = None,
        wallet_address: str | None = None,
    ) -> PartnerOrderResult: ...

    @abc.abstractmethod
    async def get_payment_instructions(self, partner_order_id: str) -> dict: ...

    @abc.abstractmethod
    async def get_order_status(self, partner_order_id: str) -> str: ...

    @abc.abstractmethod
    async def cancel_order(self, partner_order_id: str) -> bool: ...

    @abc.abstractmethod
    async def request_refund(self, partner_order_id: str, reason: str) -> str: ...

    @abc.abstractmethod
    async def get_limits(self, route: Route) -> PartnerLimits: ...

    @abc.abstractmethod
    async def get_supported_banks(self) -> list[str]: ...

    @abc.abstractmethod
    async def get_supported_payment_methods(self) -> list[str]: ...


class CryptoPartnerAdapter(BasePartnerAdapter):
    adapter_type = "crypto"

    @abc.abstractmethod
    async def get_quote(self, route: Route, amount_in: Decimal) -> PartnerQuote: ...

    @abc.abstractmethod
    async def create_order(
        self,
        route: Route,
        amount_in: Decimal,
        client_order_id: str,
        wallet_address: str | None = None,
    ) -> PartnerOrderResult: ...

    @abc.abstractmethod
    async def get_order_status(self, partner_order_id: str) -> str: ...

    @abc.abstractmethod
    async def cancel_order(self, partner_order_id: str) -> bool: ...

    @abc.abstractmethod
    async def get_supported_currencies(self) -> list[dict]: ...
