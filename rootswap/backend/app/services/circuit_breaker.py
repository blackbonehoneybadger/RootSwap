from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import CircuitBreakerState
from app.models import Partner


class CircuitBreakerService:
    def __init__(self, threshold: int | None = None, cooldown_seconds: int | None = None) -> None:
        settings = get_settings()
        self.threshold = threshold or settings.circuit_breaker_failure_threshold
        self.cooldown_seconds = cooldown_seconds or settings.circuit_breaker_cooldown_seconds

    async def record_success(self, session: AsyncSession, partner: Partner, latency_ms: float) -> None:
        partner.consecutive_failures = 0
        partner.last_success_at = datetime.now(UTC)
        partner.total_requests += 1
        partner.successful_requests += 1
        partner.average_latency_ms = (
            partner.average_latency_ms * 0.9 + latency_ms * 0.1
            if partner.average_latency_ms
            else latency_ms
        )
        if partner.total_requests:
            partner.success_rate = partner.successful_requests / partner.total_requests
        if partner.circuit_breaker_state == CircuitBreakerState.HALF_OPEN:
            partner.circuit_breaker_state = CircuitBreakerState.CLOSED
            partner.circuit_opened_at = None
            partner.cooldown_until = None

    async def record_failure(self, session: AsyncSession, partner: Partner) -> None:
        partner.consecutive_failures += 1
        partner.last_failure_at = datetime.now(UTC)
        partner.total_requests += 1
        partner.failed_requests += 1
        if partner.total_requests:
            partner.success_rate = partner.successful_requests / partner.total_requests

        if partner.circuit_breaker_state == CircuitBreakerState.HALF_OPEN:
            partner.circuit_breaker_state = CircuitBreakerState.OPEN
            partner.circuit_opened_at = datetime.now(UTC)
            partner.cooldown_until = datetime.now(UTC) + timedelta(seconds=self.cooldown_seconds)
        elif partner.consecutive_failures >= self.threshold:
            partner.circuit_breaker_state = CircuitBreakerState.OPEN
            partner.circuit_opened_at = datetime.now(UTC)
            partner.cooldown_until = datetime.now(UTC) + timedelta(seconds=self.cooldown_seconds)

    async def maybe_half_open(self, session: AsyncSession, partner: Partner) -> None:
        if partner.circuit_breaker_state != CircuitBreakerState.OPEN:
            return
        if partner.cooldown_until and datetime.now(UTC) >= partner.cooldown_until:
            partner.circuit_breaker_state = CircuitBreakerState.HALF_OPEN

    def is_available(self, partner: Partner) -> bool:
        if partner.circuit_breaker_state == CircuitBreakerState.OPEN:
            if partner.cooldown_until and datetime.now(UTC) >= partner.cooldown_until:
                return True
            return False
        return True
