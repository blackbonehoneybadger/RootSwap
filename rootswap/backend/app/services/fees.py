from app.core.enums import CircuitBreakerState


def calculate_fees(amount_in: float, partner_fee: float, network_fee: float, service_fee_rate: float) -> tuple[float, float]:
    service_fee = round(amount_in * service_fee_rate, 8)
    total_fee = round(service_fee + partner_fee + network_fee, 8)
    return service_fee, total_fee


def calculate_root_score(
    amount_out: float,
    success_rate: float,
    average_latency_ms: float,
    reserve: float,
    total_fee: float,
    estimated_time_seconds: int,
    kyc_required: bool,
    circuit_state: CircuitBreakerState,
) -> float:
    score = 0.0
    score += min(amount_out / 1000, 50)
    score += success_rate * 30
    score += max(0, 20 - average_latency_ms / 100)
    score += min(reserve / 10000, 20)
    score += max(0, 15 - total_fee)
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
    lowest_fee = min(quotes, key=lambda q: float(q.total_fee))
    return {"best": best, "fastest": fastest, "lowest_fee": lowest_fee, "all": quotes}
