"""Mock partner scenario state must not leak across adapter instances."""

import asyncio
from decimal import Decimal

import pytest

from app.core.enums import OrderDirection
from app.partners.base import PartnerError, Route
from app.partners.mock_fiat import MockFiatPartnerAdapter


@pytest.mark.asyncio
async def test_scenario_is_per_instance_not_shared():
    alpha = MockFiatPartnerAdapter(code="alpha")
    beta = MockFiatPartnerAdapter(code="beta")
    alpha.set_scenario("quote_failure")
    # beta remains success
    route = Route(OrderDirection.BUY, "RUB", None, "USDT", "TRC20")

    with pytest.raises(PartnerError):
        await alpha.get_fiat_quote(route, Decimal("10000"))

    quote = await beta.get_fiat_quote(route, Decimal("10000"))
    assert quote.amount_out > 0


@pytest.mark.asyncio
async def test_concurrent_instances_do_not_race_scenarios():
    a = MockFiatPartnerAdapter(code="a")
    b = MockFiatPartnerAdapter(code="b")
    a.set_scenario("quote_failure")
    b.set_scenario("success")
    route = Route(OrderDirection.BUY, "RUB", None, "BTC", "BTC")

    async def call_a():
        try:
            await a.get_fiat_quote(route, Decimal("10000"))
            return "ok"
        except PartnerError:
            return "fail"

    async def call_b():
        try:
            await b.get_fiat_quote(route, Decimal("10000"))
            return "ok"
        except PartnerError:
            return "fail"

    results = await asyncio.gather(*[call_a() if i % 2 == 0 else call_b() for i in range(20)])
    # Even indices use a (fail), odd use b (ok)
    assert all(r == "fail" for r in results[0::2])
    assert all(r == "ok" for r in results[1::2])
