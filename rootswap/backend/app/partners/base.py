from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class QuoteRequest:
    direction: str
    from_asset: str
    from_network: str | None
    to_asset: str
    to_network: str | None
    amount_in: float
    payment_method: str | None = None
    bank_name: str | None = None
    scenario: str | None = None


@dataclass
class QuoteResult:
    partner_code: str
    partner_order_id: str | None
    amount_out: float
    exchange_rate: float
    partner_fee: float
    network_fee: float
    estimated_time_seconds: int
    kyc_required: bool
    reserve_available: float
    raw_response: dict = field(default_factory=dict)


@dataclass
class OrderRequest:
    quote_id: str
    partner_quote_ref: str | None
    wallet_address: str | None
    payout_details: dict | None
    payment_method: str | None
    bank_name: str | None
    idempotency_key: str
    scenario: str | None = None


@dataclass
class OrderResult:
    partner_order_id: str
    status: str
    deposit_address: str | None = None
    payment_instructions: dict | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass
class PaymentInstructionsResult:
    payment_method: str
    bank_name: str | None
    recipient_name: str | None
    account_number: str | None
    card_number: str | None
    sbp_phone: str | None
    deposit_address: str | None
    amount: float
    currency: str
    payment_comment: str | None
    expires_at: datetime


@dataclass
class PartnerOrderStatus:
    partner_order_id: str
    status: str
    message: str | None = None
    raw_response: dict = field(default_factory=dict)


class FiatPartnerAdapter(ABC):
    partner_code: str

    @abstractmethod
    async def get_fiat_quote(self, request: QuoteRequest) -> QuoteResult: ...

    @abstractmethod
    async def create_fiat_order(self, request: OrderRequest) -> OrderResult: ...

    @abstractmethod
    async def get_payment_instructions(self, partner_order_id: str) -> PaymentInstructionsResult: ...

    @abstractmethod
    async def get_order_status(self, partner_order_id: str) -> PartnerOrderStatus: ...

    @abstractmethod
    async def cancel_order(self, partner_order_id: str) -> PartnerOrderStatus: ...

    @abstractmethod
    async def request_refund(self, partner_order_id: str) -> PartnerOrderStatus: ...

    @abstractmethod
    async def get_limits(self) -> dict: ...

    @abstractmethod
    async def get_supported_banks(self) -> list[str]: ...

    @abstractmethod
    async def get_supported_payment_methods(self) -> list[str]: ...

    @abstractmethod
    async def verify_webhook(self, payload: bytes, headers: dict[str, str]) -> tuple[bool, dict]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...


class CryptoPartnerAdapter(ABC):
    partner_code: str

    @abstractmethod
    async def get_quote(self, request: QuoteRequest) -> QuoteResult: ...

    @abstractmethod
    async def create_order(self, request: OrderRequest) -> OrderResult: ...

    @abstractmethod
    async def get_order_status(self, partner_order_id: str) -> PartnerOrderStatus: ...

    @abstractmethod
    async def cancel_order(self, partner_order_id: str) -> PartnerOrderStatus: ...

    @abstractmethod
    async def get_supported_currencies(self) -> list[tuple[str, str | None]]: ...

    @abstractmethod
    async def verify_webhook(self, payload: bytes, headers: dict[str, str]) -> tuple[bool, dict]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
