from datetime import timedelta

from sqlalchemy import select

from app.core.enums import CircuitBreakerState, QuoteSourceType
from app.db.base import utcnow
from app.models.partner import Partner
from app.services import circuit_breaker


async def make_partner(session, code="cb_test") -> Partner:
    partner = Partner(
        code=code, name="CB Test", adapter_type="fiat",
        quote_source_type=QuoteSourceType.MOCK, environment="mock",
    )
    session.add(partner)
    await session.commit()
    return partner


async def test_opens_after_n_consecutive_failures(session):
    partner = await make_partner(session)
    for _ in range(3):  # threshold from test settings default = 3
        await circuit_breaker.record_failure(session, partner)
    assert partner.circuit_breaker_state == CircuitBreakerState.OPEN
    assert partner.cooldown_until is not None
    assert not circuit_breaker.can_attempt(partner)


async def test_success_resets_failure_count(session):
    partner = await make_partner(session, "cb_test2")
    await circuit_breaker.record_failure(session, partner)
    await circuit_breaker.record_failure(session, partner)
    await circuit_breaker.record_success(session, partner, 100.0)
    assert partner.consecutive_failures == 0
    assert partner.circuit_breaker_state == CircuitBreakerState.CLOSED
    await circuit_breaker.record_failure(session, partner)
    assert partner.circuit_breaker_state == CircuitBreakerState.CLOSED


async def test_half_open_after_cooldown_then_close_on_success(session):
    partner = await make_partner(session, "cb_test3")
    for _ in range(3):
        await circuit_breaker.record_failure(session, partner)
    assert partner.circuit_breaker_state == CircuitBreakerState.OPEN
    # simulate cooldown elapsed
    partner.cooldown_until = utcnow() - timedelta(seconds=1)
    await session.commit()
    assert circuit_breaker.can_attempt(partner)
    circuit_breaker.to_half_open_if_ready(partner)
    assert partner.circuit_breaker_state == CircuitBreakerState.HALF_OPEN
    await circuit_breaker.record_success(session, partner, 50.0)
    assert partner.circuit_breaker_state == CircuitBreakerState.CLOSED


async def test_half_open_reopens_on_failure(session):
    partner = await make_partner(session, "cb_test4")
    for _ in range(3):
        await circuit_breaker.record_failure(session, partner)
    partner.cooldown_until = utcnow() - timedelta(seconds=1)
    circuit_breaker.to_half_open_if_ready(partner)
    assert partner.circuit_breaker_state == CircuitBreakerState.HALF_OPEN
    await circuit_breaker.record_failure(session, partner)
    assert partner.circuit_breaker_state == CircuitBreakerState.OPEN


async def test_state_persisted_in_db(session, session_factory):
    partner = await make_partner(session, "cb_test5")
    for _ in range(3):
        await circuit_breaker.record_failure(session, partner)
    await session.commit()
    async with session_factory() as other:
        row = (
            await other.execute(select(Partner).where(Partner.code == "cb_test5"))
        ).scalar_one()
        assert row.circuit_breaker_state == CircuitBreakerState.OPEN


async def test_reset(session):
    partner = await make_partner(session, "cb_test6")
    for _ in range(3):
        await circuit_breaker.record_failure(session, partner)
    await circuit_breaker.reset(session, partner)
    assert partner.circuit_breaker_state == CircuitBreakerState.CLOSED
    assert partner.consecutive_failures == 0
