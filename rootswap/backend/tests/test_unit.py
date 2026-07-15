import pytest

from app.core.enums import ActorType, CircuitBreakerState, OrderStatus
from app.core.exceptions import InvalidTransitionError, ValidationError
from app.security import mask_sensitive_data, validate_wallet_address
from app.services.fees import calculate_fees, calculate_root_score
from app.services.state_machine import OrderStateMachine


def test_calculate_fees():
    service_fee, total = calculate_fees(10000, 50, 10, 0.015)
    assert service_fee == 150.0
    assert total == 210.0


def test_root_score():
    score = calculate_root_score(
        amount_out=1000,
        success_rate=0.95,
        average_latency_ms=200,
        reserve=500000,
        total_fee=210,
        estimated_time_seconds=600,
        kyc_required=False,
        circuit_state=CircuitBreakerState.CLOSED,
    )
    assert score > 0


def test_wallet_validation_btc():
    validate_wallet_address("BTC", "BTC", "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh")


def test_wallet_validation_xmr():
    validate_wallet_address(
        "XMR",
        "XMR",
        "49" + "A" * 93,
    )


def test_wallet_validation_trc20():
    validate_wallet_address("USDT", "TRC20", "T" + "A" * 33)


def test_invalid_wallet():
    with pytest.raises(ValidationError):
        validate_wallet_address("BTC", "BTC", "invalid")


def test_state_machine_valid():
    sm = OrderStateMachine()
    assert sm.can_transition(OrderStatus.CREATED, OrderStatus.QUOTE_CONFIRMED)
    sm.validate_transition(OrderStatus.CREATED, OrderStatus.QUOTE_CONFIRMED, ActorType.SYSTEM, 1)


def test_state_machine_invalid():
    sm = OrderStateMachine()
    with pytest.raises(InvalidTransitionError):
        sm.validate_transition(OrderStatus.COMPLETED, OrderStatus.CREATED, ActorType.SYSTEM, 1)


def test_state_machine_forbids_failed_to_completed():
    sm = OrderStateMachine()
    with pytest.raises(InvalidTransitionError):
        sm.validate_transition(OrderStatus.FAILED, OrderStatus.COMPLETED, ActorType.ADMIN, 1)


def test_state_machine_forbids_cancelled_to_processing():
    sm = OrderStateMachine()
    with pytest.raises(InvalidTransitionError):
        sm.validate_transition(OrderStatus.CANCELLED, OrderStatus.PROCESSING, ActorType.SYSTEM, 1)


def test_state_machine_user_cannot_complete():
    sm = OrderStateMachine()
    with pytest.raises(InvalidTransitionError):
        sm.validate_transition(
            OrderStatus.PAYOUT_SENT, OrderStatus.COMPLETED, ActorType.USER, 1
        )


def test_state_machine_user_can_dispute():
    sm = OrderStateMachine()
    sm.validate_transition(
        OrderStatus.PAYMENT_DETECTED, OrderStatus.DISPUTED, ActorType.USER, 1
    )


def test_asset_registry_rejects_solana():
    from app.core.assets import validate_route
    from app.core.enums import OrderDirection

    with pytest.raises(ValidationError):
        validate_route(OrderDirection.BUY, "RUB", None, "SOL", "SOL", 10000)


def test_asset_registry_accepts_xmr():
    from app.core.assets import validate_route
    from app.core.enums import OrderDirection

    validate_route(OrderDirection.BUY, "RUB", None, "XMR", "XMR", 10000)


def test_mask_sensitive_data():
    masked = mask_sensitive_data({"card_number": "5536910000001234", "amount": 100})
    assert "5536" in masked["card_number"]
    assert "1234" in masked["card_number"]
    assert "*" in masked["card_number"]
