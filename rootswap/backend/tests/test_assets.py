"""Asset registry and planned-route rejection tests."""

import pytest

from app.core.assets import get_asset, list_all_assets, list_supported_assets, validate_route
from app.core.enums import OrderDirection
from app.core.exceptions import ValidationError
from app.security import validate_wallet_address


def test_sandbox_assets_are_enabled():
    for symbol, network in (("USDT", "TRC20"), ("BTC", "BTC"), ("XMR", "XMR")):
        a = get_asset(symbol, network)
        assert a is not None
        assert a.enabled is True
        assert a.status == "sandbox"


def test_planned_assets_are_not_enabled():
    for symbol, network in (
        ("ETH", "ERC20"),
        ("TON", "TON"),
        ("XRP", "XRP"),
        ("DOGE", "DOGE"),
        ("DASH", "DASH"),
        ("BNB", "BSC"),
        ("USDT", "ERC20"),
        ("USDT", "TON"),
        ("USDC", "ERC20"),
    ):
        a = get_asset(symbol, network)
        assert a is not None
        assert a.enabled is False
        assert a.status == "planned"


def test_list_supported_excludes_planned():
    supported = {(a.symbol, a.network) for a in list_supported_assets()}
    assert ("USDT", "TRC20") in supported
    assert ("ETH", "ERC20") not in supported
    assert ("XMR", "XMR") in supported  # sandbox demo only — not real money


def test_planned_route_rejected():
    with pytest.raises(ValidationError, match="planned"):
        validate_route(OrderDirection.BUY, "RUB", None, "ETH", "ERC20", 10_000)


def test_planned_ton_route_rejected():
    with pytest.raises(ValidationError, match="planned"):
        validate_route(OrderDirection.BUY, "RUB", None, "TON", "TON", 10_000)


def test_sandbox_route_accepted():
    validate_route(OrderDirection.BUY, "RUB", None, "BTC", "BTC", 10_000)


def test_xrp_memo_flag():
    a = get_asset("XRP", "XRP")
    assert a is not None
    assert a.memo_required is True


def test_bnb_is_bsc_not_beacon():
    a = get_asset("BNB", "BSC")
    assert a is not None
    assert a.chain_id == "56"
    assert "BSC" in a.name or a.network == "BSC"


def test_eth_address_format_for_planned():
    validate_wallet_address("ETH", "ERC20", "0x" + "a" * 40)
    with pytest.raises(ValidationError):
        validate_wallet_address("ETH", "ERC20", "not-an-address")


@pytest.mark.asyncio
async def test_assets_endpoint_lists_planned(client):
    r = await client.get("/api/v1/assets")
    assert r.status_code == 200
    data = r.json()
    symbols = {(a["symbol"], a["network"]) for a in data["assets"]}
    assert ("ETH", "ERC20") in symbols
    eth = next(a for a in data["assets"] if a["symbol"] == "ETH")
    assert eth["status"] == "planned"
    assert eth["enabled"] is False
    assert "sandbox" in data["note"].lower() or "planned" in data["note"].lower()
    assert len(list_all_assets()) >= 10


@pytest.mark.asyncio
async def test_planned_asset_cannot_create_quote(client, auth_headers):
    r = await client.post(
        "/api/v1/quotes",
        headers=auth_headers,
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "ETH",
            "to_network": "ERC20",
            "amount_in": 10000,
            "payment_method": "SBP",
            "bank_name": "Sber",
        },
    )
    assert r.status_code == 400
    assert "planned" in r.text.lower() or "unsupported" in r.text.lower()
