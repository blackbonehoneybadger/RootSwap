from decimal import Decimal

from app.core.enums import CircuitBreakerState
from app.core.money import D, q8


def calculate_fees(
    amount_in: Decimal | float | str,
    partner_fee: Decimal | float | str,
    network_fee: Decimal | float | str,
    service_fee_rate: Decimal | float | str,
) -> tuple[Decimal, Decimal]:
    amount = D(amount_in)
    service_fee = q8(amount * D(service_fee_rate))
    total_fee = q8(service_fee + D(partner_fee) + D(network_fee))
    return service_fee, total_fee


def calculate_root_score(
    amount_out: Decimal | float | str,
    success_rate: float,
    average_latency_ms: float,
    reserve: Decimal | float | str,
    total_fee: Decimal | float | str,
    estimated_time_seconds: int,
    kyc_required: bool,
    circuit_state: CircuitBreakerState,
) -> float:
    amount_out_f = float(D(amount_out))
    reserve_f = float(D(reserve))
    total_fee_f = float(D(total_fee))
    score = 0.0
    score += min(amount_out_f / 1000, 50)
    score += success_rate * 30
    score += max(0, 20 - average_latency_ms / 100)
    score += min(reserve_f / 10000, 20)
    score += max(0, 15 - total_fee_f)
    score += max(0, 10 - estimated_time_seconds / 60)
    if not kyc_required:
        score += 5
    if circuit_state == CircuitBreakerState.CLOSED:
        score += 10
    elif circuit_state == CircuitBreakerState.HALF_OPEN:
        score += 3
    return round(score, 4)


def _estimated_time(quote) -> int:
    raw = quote.raw_partner_response or {}
    return int(raw.get("estimated_time_seconds", 9999))


def classify_quotes(quotes: list) -> dict:
    if not quotes:
        return {"best": None, "fastest": None, "lowest_fee": None, "all": []}
    best = max(quotes, key=lambda q: q.root_score)
    fastest = min(quotes, key=_estimated_time)
    lowest_fee = min(quotes, key=lambda q: D(q.total_fee))
    return {"best": best, "fastest": fastest, "lowest_fee": lowest_fee, "all": quotes}
