from app.core.enums import ActorType, OrderDirection, OrderStatus
from app.core.exceptions import InvalidTransitionError

# Single source of truth for allowed status transitions.
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.QUOTE_CONFIRMED, OrderStatus.CANCELLED, OrderStatus.FAILED},
    OrderStatus.QUOTE_CONFIRMED: {
        OrderStatus.AWAITING_PAYMENT,
        OrderStatus.CANCELLED,
        OrderStatus.FAILED,
    },
    OrderStatus.AWAITING_PAYMENT: {
        OrderStatus.PAYMENT_DETECTED,
        OrderStatus.EXPIRED,
        OrderStatus.CANCELLED,
        OrderStatus.FAILED,
    },
    OrderStatus.PAYMENT_DETECTED: {
        OrderStatus.PAYMENT_CONFIRMING,
        OrderStatus.DISPUTED,
        OrderStatus.FAILED,
    },
    OrderStatus.PAYMENT_CONFIRMING: {
        OrderStatus.PROCESSING,
        OrderStatus.DISPUTED,
        OrderStatus.FAILED,
    },
    OrderStatus.PROCESSING: {
        OrderStatus.PAYOUT_SENT,
        OrderStatus.FAILED,
        OrderStatus.DISPUTED,
    },
    OrderStatus.PAYOUT_SENT: {OrderStatus.COMPLETED, OrderStatus.FAILED},
    OrderStatus.COMPLETED: {OrderStatus.REFUND_REQUESTED, OrderStatus.DISPUTED},
    OrderStatus.REFUND_REQUESTED: {OrderStatus.REFUND_PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.REFUND_PROCESSING: {OrderStatus.REFUNDED, OrderStatus.REFUND_FAILED},
    OrderStatus.DISPUTED: {
        OrderStatus.PROCESSING,
        OrderStatus.REFUND_REQUESTED,
        OrderStatus.CANCELLED,
    },
    # Terminal / recovery-limited:
    # EXPIRED, FAILED, CANCELLED, REFUNDED, REFUND_FAILED — no outbound transitions.
}

# USER may only initiate cancellations / disputes (never fake COMPLETED).
USER_ALLOWED_TARGETS: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.CANCELLED,
        OrderStatus.DISPUTED,
    }
)

BUY_CHAIN = [
    OrderStatus.CREATED,
    OrderStatus.QUOTE_CONFIRMED,
    OrderStatus.AWAITING_PAYMENT,
    OrderStatus.PAYMENT_DETECTED,
    OrderStatus.PAYMENT_CONFIRMING,
    OrderStatus.PROCESSING,
    OrderStatus.PAYOUT_SENT,
    OrderStatus.COMPLETED,
]

SELL_CHAIN = BUY_CHAIN


class OrderStateMachine:
    def can_transition(self, current: OrderStatus, target: OrderStatus) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        return target in allowed

    def validate_transition(
        self,
        current: OrderStatus,
        target: OrderStatus,
        actor: ActorType | None,
        order_version: int,
        expected_version: int | None = None,
    ) -> None:
        if expected_version is not None and order_version != expected_version:
            raise InvalidTransitionError(
                f"Version mismatch: expected {expected_version}, got {order_version}"
            )
        if not self.can_transition(current, target):
            raise InvalidTransitionError(
                f"Transition from {current.value} to {target.value} is not allowed"
            )
        if actor == ActorType.USER and target not in USER_ALLOWED_TARGETS:
            raise InvalidTransitionError(
                f"USER cannot transition to {target.value}"
            )

    def get_chain(self, direction: OrderDirection) -> list[OrderStatus]:
        return BUY_CHAIN if direction == OrderDirection.BUY else SELL_CHAIN
