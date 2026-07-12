"""Domain enums for RootSwap."""

import enum


class OrderDirection(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class QuoteSourceType(str, enum.Enum):
    MOCK = "MOCK"
    SANDBOX = "SANDBOX"
    REAL = "REAL"


class OrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    QUOTE_CONFIRMED = "QUOTE_CONFIRMED"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAYMENT_DETECTED = "PAYMENT_DETECTED"
    PAYMENT_CONFIRMING = "PAYMENT_CONFIRMING"
    PROCESSING = "PROCESSING"
    PAYOUT_SENT = "PAYOUT_SENT"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    DISPUTED = "DISPUTED"
    REFUND_REQUESTED = "REFUND_REQUESTED"
    REFUND_PROCESSING = "REFUND_PROCESSING"
    REFUNDED = "REFUNDED"
    REFUND_FAILED = "REFUND_FAILED"
    CANCELLED = "CANCELLED"


FINAL_ORDER_STATUSES = frozenset(
    {
        OrderStatus.COMPLETED,
        OrderStatus.REFUNDED,
        OrderStatus.FAILED,
        OrderStatus.EXPIRED,
        OrderStatus.CANCELLED,
    }
)


class CircuitBreakerState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class LedgerEntryType(str, enum.Enum):
    GROSS_SERVICE_FEE = "GROSS_SERVICE_FEE"
    PARTNER_REWARD = "PARTNER_REWARD"
    PARTNER_COST = "PARTNER_COST"
    NETWORK_COST = "NETWORK_COST"
    REFERRAL_LIABILITY = "REFERRAL_LIABILITY"
    REFERRAL_PAID = "REFERRAL_PAID"
    REFUND_LIABILITY = "REFUND_LIABILITY"
    REFUND_PAID = "REFUND_PAID"
    ADJUSTMENT = "ADJUSTMENT"
    REALIZED_NET_PROFIT = "REALIZED_NET_PROFIT"


class AdminRole(str, enum.Enum):
    SUPPORT = "SUPPORT"
    OPERATIONS = "OPERATIONS"
    FINANCE = "FINANCE"
    ADMIN = "ADMIN"


# Role hierarchy: higher number => more privileges.
ADMIN_ROLE_RANK = {
    AdminRole.SUPPORT: 1,
    AdminRole.OPERATIONS: 2,
    AdminRole.FINANCE: 3,
    AdminRole.ADMIN: 4,
}


class ActorType(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    PARTNER = "PARTNER"
    SYSTEM = "SYSTEM"


class PaymentMethod(str, enum.Enum):
    SBP = "SBP"
    BANK_TRANSFER = "bank_transfer"
    CARD_TRANSFER = "card_transfer"


class DisputeStatus(str, enum.Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class RiskFlagStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class ReferralRewardStatus(str, enum.Enum):
    PENDING = "PENDING"
    FROZEN = "FROZEN"
    CONFIRMED = "CONFIRMED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class WebhookProcessingStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    DUPLICATE = "DUPLICATE"
    RETRYING = "RETRYING"
    DEAD_LETTER = "DEAD_LETTER"
    REJECTED = "REJECTED"
