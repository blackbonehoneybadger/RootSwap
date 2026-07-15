from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.core.enums import OrderDirection, OrderStatus, QuoteSourceType
from app.core.money import D, money_to_json, q8

Money = Annotated[Decimal, Field()]


def _parse_money(v: Any) -> Decimal:
    return q8(D(v))


class TelegramAuthRequest(BaseModel):
    init_data: str
    referral_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID


class QuoteCreateRequest(BaseModel):
    direction: OrderDirection
    from_asset: str
    from_network: str | None = None
    to_asset: str
    to_network: str | None = None
    amount_in: Money = Field(gt=0)
    payment_method: str | None = None
    bank_name: str | None = None
    scenario: str | None = None

    @field_validator("amount_in", mode="before")
    @classmethod
    def _amount_in(cls, v: Any) -> Decimal:
        return _parse_money(v)


class QuoteResponse(BaseModel):
    id: UUID
    partner_code: str
    direction: OrderDirection
    from_asset: str
    from_network: str | None
    to_asset: str
    to_network: str | None
    amount_in: Money
    amount_out: Money
    exchange_rate: Money
    service_fee: Money
    partner_fee: Money
    network_fee: Money
    total_fee: Money
    root_score: float
    quote_source_type: QuoteSourceType
    expires_at: datetime
    kyc_required: bool = False
    estimated_time_seconds: int = 600

    model_config = {"from_attributes": True}

    @field_serializer(
        "amount_in",
        "amount_out",
        "exchange_rate",
        "service_fee",
        "partner_fee",
        "network_fee",
        "total_fee",
    )
    def _ser_money(self, v: Decimal) -> float:
        return money_to_json(v)


class QuoteListResponse(BaseModel):
    best: QuoteResponse | None
    fastest: QuoteResponse | None
    lowest_fee: QuoteResponse | None
    all: list[QuoteResponse]


class OrderCreateRequest(BaseModel):
    quote_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)
    wallet_address: str | None = None
    payout_details: dict | None = None
    payment_method: str | None = None
    bank_name: str | None = None
    scenario: str | None = None


class PaymentInstructionsResponse(BaseModel):
    id: UUID
    payment_method: str
    bank_name: str | None
    masked_recipient_name: str | None
    masked_account: str | None
    masked_card: str | None
    masked_phone: str | None
    deposit_address_masked: str | None
    amount: Money
    currency: str
    payment_comment: str | None
    expires_at: datetime
    recipient_name: str | None = None
    account_number: str | None = None
    card_number: str | None = None
    sbp_phone: str | None = None
    deposit_address: str | None = None

    model_config = {"from_attributes": True}

    @field_serializer("amount")
    def _ser_amount(self, v: Decimal) -> float:
        return money_to_json(v)


class OrderResponse(BaseModel):
    id: UUID
    quote_id: UUID
    partner_code: str
    partner_order_id: str | None
    direction: OrderDirection
    status: OrderStatus
    from_asset: str
    from_network: str | None
    to_asset: str
    to_network: str | None
    amount_in: Money
    amount_out: Money
    exchange_rate: Money
    service_fee: Money
    partner_fee: Money
    network_fee: Money
    total_fee: Money
    quote_source_type: QuoteSourceType
    wallet_address_masked: str | None
    payout_details_masked: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    expired_at: datetime | None
    payment_instructions: PaymentInstructionsResponse | None = None

    model_config = {"from_attributes": True}

    @field_serializer(
        "amount_in",
        "amount_out",
        "exchange_rate",
        "service_fee",
        "partner_fee",
        "network_fee",
        "total_fee",
    )
    def _ser_money(self, v: Decimal) -> float:
        return money_to_json(v)


class DisputeCreateRequest(BaseModel):
    reason: str


class ReferralStatsResponse(BaseModel):
    referral_code: str
    referral_link: str
    referred_count: int
    active_referred_users: int
    total_rewards: float
    rewards: list[dict]


class AdminTransitionRequest(BaseModel):
    target_status: OrderStatus
    reason: str | None = None
    expected_version: int | None = None


class AdminRefundRequest(BaseModel):
    amount: Money = Field(gt=0)
    reason: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, v: Any) -> Decimal:
        return _parse_money(v)


class AdminDisablePartnerRequest(BaseModel):
    reason: str | None = None
