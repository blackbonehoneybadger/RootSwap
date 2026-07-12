"""Per-partner circuit breaker, state persisted on the partners table.

CLOSED -> (N consecutive failures) -> OPEN -> (cooldown elapses) -> HALF_OPEN ->
one probe -> success: CLOSED / failure: OPEN again.
"""

import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import CircuitBreakerState
from app.db.base import utcnow
from app.models.partner import Partner
from app.observability.metrics import metrics

logger = logging.getLogger(__name__)


def can_attempt(partner: Partner) -> bool:
    """True when the partner may be called (CLOSED, HALF_OPEN, or cooldown elapsed)."""
    if partner.circuit_breaker_state == CircuitBreakerState.CLOSED:
        return True
    if partner.circuit_breaker_state == CircuitBreakerState.HALF_OPEN:
        return True
    # OPEN: allow a probe once cooldown has passed
    return partner.cooldown_until is not None and partner.cooldown_until <= utcnow()


def to_half_open_if_ready(partner: Partner) -> None:
    if (
        partner.circuit_breaker_state == CircuitBreakerState.OPEN
        and partner.cooldown_until is not None
        and partner.cooldown_until <= utcnow()
    ):
        partner.circuit_breaker_state = CircuitBreakerState.HALF_OPEN


async def record_success(session: AsyncSession, partner: Partner, latency_ms: float = 0.0) -> None:
    partner.total_requests += 1
    partner.successful_requests += 1
    partner.consecutive_failures = 0
    partner.last_success_at = utcnow()
    if partner.total_requests:
        partner.success_rate = partner.successful_requests / partner.total_requests
    # exponential moving average
    partner.average_latency_ms = (
        latency_ms
        if partner.average_latency_ms == 0
        else partner.average_latency_ms * 0.8 + latency_ms * 0.2
    )
    if partner.circuit_breaker_state != CircuitBreakerState.CLOSED:
        partner.circuit_breaker_state = CircuitBreakerState.CLOSED
        partner.circuit_opened_at = None
        partner.cooldown_until = None
        metrics.inc("circuit_breaker_closed_total", partner=partner.code)
    await session.flush()


async def record_failure(session: AsyncSession, partner: Partner) -> None:
    settings = get_settings()
    partner.total_requests += 1
    partner.failed_requests += 1
    partner.consecutive_failures += 1
    partner.last_failure_at = utcnow()
    if partner.total_requests:
        partner.success_rate = partner.successful_requests / partner.total_requests

    if partner.circuit_breaker_state == CircuitBreakerState.HALF_OPEN:
        _open(partner, settings.circuit_breaker_cooldown_seconds)
    elif (
        partner.circuit_breaker_state == CircuitBreakerState.CLOSED
        and partner.consecutive_failures >= settings.circuit_breaker_failure_threshold
    ):
        _open(partner, settings.circuit_breaker_cooldown_seconds)
    await session.flush()


def _open(partner: Partner, cooldown_seconds: int) -> None:
    partner.circuit_breaker_state = CircuitBreakerState.OPEN
    partner.circuit_opened_at = utcnow()
    partner.cooldown_until = utcnow() + timedelta(seconds=cooldown_seconds)
    metrics.inc("circuit_breaker_opened_total", partner=partner.code)
    logger.warning("circuit breaker opened", extra={"ctx": {"partner": partner.code}})


async def reset(session: AsyncSession, partner: Partner) -> None:
    partner.circuit_breaker_state = CircuitBreakerState.CLOSED
    partner.consecutive_failures = 0
    partner.circuit_opened_at = None
    partner.cooldown_until = None
    await session.flush()
