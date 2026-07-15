from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import OrderDirection, OrderStatus, QuoteSourceType


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
    amount_in: float = Field(gt=0)
    payment_method: str | None = None
    bank_name: str | None = None
    scenario: str | None = None


class QuoteResponse(BaseModel):
    id: UUID
    partner_code: str
    direction: OrderDirection
    from_asset: str
    from_network: str | None
    to_asset: str
    to_network: str | None
    amount_in: float
    amount_out: float
    exchange_rate: float
    service_fee: float
    partner_fee: float
    network_fee: float
    total_fee: float
    root_score: float
    quote_source_type: QuoteSourceType
    expires_at: datetime
    kyc_required: bool = False
    estimated_time_seconds: int = 600

    model_config = {"from_attributes": True}


class QuoteListResponse(BaseModel):
    best: QuoteResponse | None
    fastest: QuoteResponse | None
    lowest_fee: QuoteResponse | None
    all: list[QuoteResponse]


class OrderCreateRequest(BaseModel):
    quote_id: UUID
    idempotency_key: str
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
    amount: float
    currency: str
    payment_comment: str | None
    expires_at: datetime
    # Revealed only for MOCK/SANDBOX demo copy-paste
    recipient_name: str | None = None
    account_number: str | None = None
    card_number: str | None = None
    sbp_phone: str | None = None
    deposit_address: str | None = None

    model_config = {"from_attributes": True}


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
    amount_in: float
    amount_out: float
    exchange_rate: float
    service_fee: float
    partner_fee: float
    network_fee: float
    total_fee: float
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
    amount: float
    reason: str | None = None


class AdminDisablePartnerRequest(BaseModel):
    reason: str | None = None
