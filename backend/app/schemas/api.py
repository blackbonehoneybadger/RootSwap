"""Pydantic request/response schemas for the public API."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.enums import OrderDirection


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=8192)
    referral_code: str | None = Field(default=None, max_length=16)


class UserOut(BaseModel):
    id: str
    telegram_id: int
    username: str | None
    first_name: str | None
    referral_code: str


class TelegramAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class QuoteRequest(BaseModel):
    direction: OrderDirection
    from_asset: str = Field(max_length=16)
    from_network: str | None = Field(default=None, max_length=16)
    to_asset: str = Field(max_length=16)
    to_network: str | None = Field(default=None, max_length=16)
    amount_in: Decimal = Field(gt=0)
    payment_method: str | None = Field(default=None, max_length=32)
    bank: str | None = Field(default=None, max_length=32)

    @field_validator("amount_in")
    @classmethod
    def sane_amount(cls, value: Decimal) -> Decimal:
        if value > Decimal("1000000000"):
            raise ValueError("amount too large")
        return value


class QuoteOut(BaseModel):
    quote_id: str
    partner_code: str
    partner_name: str
    direction: OrderDirection
    from_asset: str
    from_network: str | None
    to_asset: str
    to_network: str | None
    amount_in: str
    amount_out: str
    exchange_rate: str
    service_fee: str
    partner_fee: str
    network_fee: str
    total_fee: str
    root_score: str
    quote_source_type: str
    expires_at: str
    kyc_required: bool
    estimated_time_minutes: int
    labels: list[str]


class QuotesResponse(BaseModel):
    quotes: list[QuoteOut]


class PayoutDetails(BaseModel):
    payment_method: str = Field(max_length=32)
    bank: str | None = Field(default=None, max_length=32)
    account: str = Field(min_length=4, max_length=64)


class CreateOrderRequest(BaseModel):
    quote_id: str = Field(max_length=36)
    idempotency_key: str = Field(min_length=8, max_length=64)
    wallet_address: str | None = Field(default=None, max_length=128)
    payout_details: PayoutDetails | None = None
    payment_method: str | None = Field(default=None, max_length=32)
    bank: str | None = Field(default=None, max_length=32)


class PaymentInstructionsOut(BaseModel):
    payment_method: str
    bank_name: str | None
    masked_recipient_name: str | None
    masked_account: str | None
    masked_card: str | None
    masked_phone: str | None
    amount: str
    currency: str
    payment_comment: str | None
    expires_at: str
    # Full values revealed only for MOCK/SANDBOX demo flows (never in REAL/production UI)
    recipient_name: str | None = None
    account_number: str | None = None
    card_number: str | None = None
    sbp_phone: str | None = None


class OrderEventOut(BaseModel):
    status: str
    message: str | None
    created_at: str


class OrderOut(BaseModel):
    id: str
    status: str
    direction: OrderDirection
    from_asset: str
    from_network: str | None
    to_asset: str
    to_network: str | None
    amount_in: str
    amount_out: str
    exchange_rate: str
    service_fee: str
    partner_fee: str
    network_fee: str
    total_fee: str
    quote_source_type: str
    wallet_address_masked: str | None
    payout_details_masked: str | None
    deposit_address: str | None
    deposit_network: str | None
    payment_instructions: PaymentInstructionsOut | None
    events: list[OrderEventOut]
    created_at: str


class OrdersResponse(BaseModel):
    orders: list[OrderOut]


class DisputeRequest(BaseModel):
    reason: str = Field(min_length=4, max_length=512)


class AdminTransitionRequest(BaseModel):
    target_status: str
    reason: str = Field(min_length=4, max_length=512)
    expected_version: int | None = None


class AdminRefundRequest(BaseModel):
    reason: str = Field(min_length=4, max_length=512)


class EmergencyStopRequest(BaseModel):
    reason: str = Field(min_length=4, max_length=512)
