from decimal import Decimal

from app.core.enums import CircuitBreakerState
from app.services.root_score import compute_root_score


def _score(**overrides):
    params = dict(
        amount_out=Decimal("100"),
        best_amount_out=Decimal("100"),
        total_fee=Decimal("10"),
        lowest_total_fee=Decimal("10"),
        partner_success_rate=1.0,
        average_latency_ms=100.0,
        reserve_available=True,
        estimated_time_minutes=10,
        kyc_required=False,
        circuit_state=CircuitBreakerState.CLOSED,
    )
    params.update(overrides)
    return compute_root_score(**params)


def test_perfect_partner_scores_high():
    assert _score() > Decimal("95")


def test_score_bounded_0_100():
    assert Decimal("0") <= _score() <= Decimal("100")
    low = _score(
        amount_out=Decimal("1"),
        partner_success_rate=0.0,
        average_latency_ms=10000.0,
        reserve_available=False,
        total_fee=Decimal("100"),
        estimated_time_minutes=300,
        kyc_required=True,
        circuit_state=CircuitBreakerState.OPEN,
    )
    assert Decimal("0") <= low <= Decimal("100")


def test_better_amount_out_wins():
    assert _score(amount_out=Decimal("100")) > _score(amount_out=Decimal("90"))


def test_kyc_penalty():
    assert _score(kyc_required=False) > _score(kyc_required=True)


def test_low_success_rate_penalty():
    assert _score(partner_success_rate=1.0) > _score(partner_success_rate=0.5)


def test_half_open_scores_between_closed_and_open():
    closed = _score(circuit_state=CircuitBreakerState.CLOSED)
    half = _score(circuit_state=CircuitBreakerState.HALF_OPEN)
    opened = _score(circuit_state=CircuitBreakerState.OPEN)
    assert closed > half > opened
