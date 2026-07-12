"""RootScore: 0..100 ranking score for partner quotes.

Factors: amount_out (relative to best), partner success rate, average latency,
reserve availability, total fee (relative), estimated time, KYC requirement,
circuit breaker state.
"""

from decimal import Decimal

from app.core.enums import CircuitBreakerState

WEIGHTS = {
    "amount_out": Decimal("35"),
    "success_rate": Decimal("20"),
    "latency": Decimal("10"),
    "reserve": Decimal("10"),
    "fee": Decimal("10"),
    "estimated_time": Decimal("5"),
    "kyc": Decimal("5"),
    "circuit": Decimal("5"),
}


def compute_root_score(
    amount_out: Decimal,
    best_amount_out: Decimal,
    total_fee: Decimal,
    lowest_total_fee: Decimal,
    partner_success_rate: float,
    average_latency_ms: float,
    reserve_available: bool,
    estimated_time_minutes: int,
    kyc_required: bool,
    circuit_state: CircuitBreakerState,
) -> Decimal:
    score = Decimal("0")

    if best_amount_out > 0:
        score += WEIGHTS["amount_out"] * (amount_out / best_amount_out)

    score += WEIGHTS["success_rate"] * Decimal(str(max(0.0, min(1.0, partner_success_rate))))

    # 0ms -> full, >=5000ms -> zero
    latency_factor = max(Decimal("0"), Decimal("1") - Decimal(str(average_latency_ms)) / Decimal("5000"))
    score += WEIGHTS["latency"] * latency_factor

    if reserve_available:
        score += WEIGHTS["reserve"]

    if total_fee <= 0:
        score += WEIGHTS["fee"]
    elif lowest_total_fee > 0:
        score += WEIGHTS["fee"] * min(Decimal("1"), lowest_total_fee / total_fee)

    # <=10 min -> full, >=120 min -> zero
    time_factor = max(
        Decimal("0"),
        min(Decimal("1"), (Decimal("120") - Decimal(estimated_time_minutes)) / Decimal("110")),
    )
    score += WEIGHTS["estimated_time"] * time_factor

    if not kyc_required:
        score += WEIGHTS["kyc"]

    if circuit_state == CircuitBreakerState.CLOSED:
        score += WEIGHTS["circuit"]
    elif circuit_state == CircuitBreakerState.HALF_OPEN:
        score += WEIGHTS["circuit"] / 2

    return score.quantize(Decimal("0.01"))
