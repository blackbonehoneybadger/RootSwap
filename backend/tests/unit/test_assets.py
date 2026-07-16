"""Asset registry and planned-route rejection."""

from decimal import Decimal

import pytest

from app.core.assets import get_asset, list_tradeable_assets, validate_route
from app.core.enums import OrderDirection
from app.core.errors import ValidationFailedError
from app.services.wallet_validation import validate_wallet_address


def test_sandbox_assets_enabled():
    for symbol, network in (("USDT", "TRC20"), ("BTC", "BTC"), ("XMR", "XMR")):
        a = get_asset(symbol, network)
        assert a is not None
        assert a.enabled is True
        assert a.status == "sandbox"
        assert isinstance(a.min_amount, Decimal)


def test_planned_assets_disabled():
    for symbol, network in (
        ("ETH", "ERC20"),
        ("TON", "TON"),
        ("SOL", "SOL"),
        ("XRP", "XRP"),
        ("DOGE", "DOGE"),
        ("DASH", "DASH"),
        ("BNB", "BSC"),
    ):
        a = get_asset(symbol, network)
        assert a is not None
        assert a.enabled is False
        assert a.status == "planned"


def test_no_real_assets_yet():
    assert all(a.status != "real" for a in list_tradeable_assets())


def test_planned_route_rejected():
    with pytest.raises(ValidationFailedError, match="planned"):
        validate_route(OrderDirection.BUY, "RUB", None, "ETH", "ERC20", Decimal("10000"))


def test_sandbox_route_ok():
    validate_route(OrderDirection.BUY, "RUB", None, "BTC", "BTC", Decimal("10000"))


def test_eth_format_validation():
    validate_wallet_address("ETH", "ERC20", "0x" + "a" * 40)
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("ETH", "ERC20", "not-an-address")


@pytest.mark.asyncio
async def test_assets_endpoint(client):
    r = await client.get("/api/v1/assets")
    assert r.status_code == 200
    body = r.json()
    eth = next(a for a in body["assets"] if a["symbol"] == "ETH")
    assert eth["status"] == "planned"
    assert eth["enabled"] is False
    assert isinstance(eth["min_amount"], str)


@pytest.mark.asyncio
async def test_planned_quote_rejected_via_api(client):
    from tests.conftest import authed_user

    headers, _ = await authed_user(client)
    r = await client.post(
        "/api/v1/quotes",
        headers=headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "TON",
            "to_network": "TON",
            "amount_in": "10000",
        },
    )
    assert r.status_code == 422
    assert "planned" in r.text.lower()
