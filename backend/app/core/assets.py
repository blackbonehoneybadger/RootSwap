"""Canonical asset / network registry.

Status model (honest):
- sandbox — available via MOCK/SANDBOX partners only (demo)
- planned — listed for roadmap; cannot create quotes/orders
- disabled — hidden from buy flow
- real — live partner adapter + E2E + compliance (none yet)

A coin is "real" only with a contracted REAL partner adapter and passing E2E.
XMR / TON / SOL are NOT live products in this build.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from app.core.enums import OrderDirection
from app.core.errors import ValidationFailedError


@dataclass(frozen=True, slots=True)
class AssetSpec:
    symbol: str
    name: str
    network: str | None
    decimals: int
    enabled: bool
    min_amount: Decimal
    max_amount: Decimal
    status: str  # sandbox | planned | disabled | real
    address_hint: str = ""
    memo_required: bool = False
    explorer_url: str | None = None
    chain_id: str | None = None
    icon: str = ""
    partner_availability: str = "none"  # none | mock | real


def _a(
    symbol: str,
    name: str,
    network: str | None,
    decimals: int,
    *,
    enabled: bool,
    status: str,
    min_amount: str,
    max_amount: str,
    address_hint: str = "",
    memo_required: bool = False,
    explorer_url: str | None = None,
    chain_id: str | None = None,
    icon: str = "",
    partner_availability: str = "none",
) -> AssetSpec:
    return AssetSpec(
        symbol=symbol,
        name=name,
        network=network,
        decimals=decimals,
        enabled=enabled,
        min_amount=Decimal(min_amount),
        max_amount=Decimal(max_amount),
        status=status,
        address_hint=address_hint,
        memo_required=memo_required,
        explorer_url=explorer_url,
        chain_id=chain_id,
        icon=icon or symbol,
        partner_availability=partner_availability,
    )


ASSETS: dict[tuple[str, str | None], AssetSpec] = {
    ("RUB", None): _a(
        "RUB", "Russian Ruble", None, 2, enabled=True, status="sandbox",
        min_amount="1000", max_amount="500000", partner_availability="mock",
    ),
    ("USDT", "TRC20"): _a(
        "USDT", "Tether USD", "TRC20", 6, enabled=True, status="sandbox",
        min_amount="10", max_amount="20000", address_hint="T… (TRON)",
        explorer_url="https://tronscan.org/#/address/{address}",
        partner_availability="mock",
    ),
    ("BTC", "BTC"): _a(
        "BTC", "Bitcoin", "BTC", 8, enabled=True, status="sandbox",
        min_amount="0.0001", max_amount="2", address_hint="bc1… / 1… / 3…",
        explorer_url="https://mempool.space/address/{address}",
        partner_availability="mock",
    ),
    ("XMR", "XMR"): _a(
        "XMR", "Monero", "XMR", 12, enabled=True, status="sandbox",
        min_amount="0.01", max_amount="200", address_hint="4… / 8… primary",
        partner_availability="mock",
    ),
    # Planned — no adapter route; UI shows «Скоро»
    ("ETH", "ERC20"): _a(
        "ETH", "Ethereum", "ERC20", 18, enabled=False, status="planned",
        min_amount="0.01", max_amount="50", address_hint="0x…", chain_id="1",
        explorer_url="https://etherscan.io/address/{address}",
    ),
    ("USDT", "ERC20"): _a(
        "USDT", "Tether USD", "ERC20", 6, enabled=False, status="planned",
        min_amount="10", max_amount="20000", address_hint="0x…", chain_id="1",
    ),
    ("USDC", "ERC20"): _a(
        "USDC", "USD Coin", "ERC20", 6, enabled=False, status="planned",
        min_amount="10", max_amount="20000", address_hint="0x…", chain_id="1",
    ),
    ("USDT", "SOL"): _a(
        "USDT", "Tether USD", "SOL", 6, enabled=False, status="planned",
        min_amount="10", max_amount="20000", address_hint="Solana base58",
    ),
    ("USDC", "SOL"): _a(
        "USDC", "USD Coin", "SOL", 6, enabled=False, status="planned",
        min_amount="10", max_amount="20000",
    ),
    ("SOL", "SOL"): _a(
        "SOL", "Solana", "SOL", 9, enabled=False, status="planned",
        min_amount="0.1", max_amount="5000",
    ),
    ("TON", "TON"): _a(
        "TON", "Toncoin", "TON", 9, enabled=False, status="planned",
        min_amount="1", max_amount="50000", address_hint="EQ… / UQ…",
    ),
    ("USDT", "TON"): _a(
        "USDT", "Tether USD", "TON", 6, enabled=False, status="planned",
        min_amount="10", max_amount="20000", memo_required=True,
    ),
    ("XRP", "XRP"): _a(
        "XRP", "XRP", "XRP", 6, enabled=False, status="planned",
        min_amount="10", max_amount="100000", memo_required=True,
        address_hint="r… + destination tag",
    ),
    ("DOGE", "DOGE"): _a(
        "DOGE", "Dogecoin", "DOGE", 8, enabled=False, status="planned",
        min_amount="50", max_amount="5000000",
    ),
    ("DASH", "DASH"): _a(
        "DASH", "Dash", "DASH", 8, enabled=False, status="planned",
        min_amount="0.1", max_amount="5000",
    ),
    ("BNB", "BSC"): _a(
        "BNB", "BNB (BSC)", "BSC", 18, enabled=False, status="planned",
        min_amount="0.05", max_amount="500", chain_id="56",
        address_hint="0x… BNB Smart Chain",
    ),
    ("USDT", "BSC"): _a(
        "USDT", "Tether USD", "BSC", 18, enabled=False, status="planned",
        min_amount="10", max_amount="20000", chain_id="56",
    ),
}

# Routes implemented by mock fiat partners today.
SUPPORTED_ROUTES: list[tuple[OrderDirection, str, str | None, str, str | None]] = [
    (OrderDirection.BUY, "RUB", None, "USDT", "TRC20"),
    (OrderDirection.BUY, "RUB", None, "BTC", "BTC"),
    (OrderDirection.BUY, "RUB", None, "XMR", "XMR"),
    (OrderDirection.SELL, "USDT", "TRC20", "RUB", None),
    (OrderDirection.SELL, "BTC", "BTC", "RUB", None),
    (OrderDirection.SELL, "XMR", "XMR", "RUB", None),
]


def _key(symbol: str, network: str | None) -> tuple[str, str | None]:
    return (symbol.upper(), network.upper() if network else None)


def get_asset(symbol: str, network: str | None) -> AssetSpec | None:
    return ASSETS.get(_key(symbol, network))


def list_tradeable_assets() -> list[AssetSpec]:
    return [a for a in ASSETS.values() if a.enabled and a.status in ("sandbox", "real")]


def list_all_assets() -> list[AssetSpec]:
    return list(ASSETS.values())


def asset_to_dict(a: AssetSpec) -> dict:
    d = asdict(a)
    d["min_amount"] = format(a.min_amount, "f")
    d["max_amount"] = format(a.max_amount, "f")
    return d


def validate_route(
    direction: OrderDirection,
    from_asset: str,
    from_network: str | None,
    to_asset: str,
    to_network: str | None,
    amount_in: Decimal,
) -> None:
    route = (
        direction,
        from_asset.upper(),
        from_network.upper() if from_network else None,
        to_asset.upper(),
        to_network.upper() if to_network else None,
    )
    if route not in SUPPORTED_ROUTES:
        target = get_asset(
            to_asset if direction == OrderDirection.BUY else from_asset,
            to_network if direction == OrderDirection.BUY else from_network,
        )
        if target and target.status == "planned":
            raise ValidationFailedError(
                f"{target.symbol}/{target.network} is planned — not available for quotes yet"
            )
        raise ValidationFailedError(
            f"Unsupported route: {direction.value} "
            f"{from_asset}/{from_network} → {to_asset}/{to_network}"
        )

    if direction == OrderDirection.BUY:
        fiat = get_asset("RUB", None)
        assert fiat is not None
        if amount_in < fiat.min_amount or amount_in > fiat.max_amount:
            raise ValidationFailedError(
                f"amount_in must be between {fiat.min_amount} and {fiat.max_amount} RUB"
            )
        crypto = get_asset(to_asset, to_network)
        if not crypto or not crypto.enabled:
            raise ValidationFailedError(f"Asset {to_asset}/{to_network} is not enabled")
    else:
        crypto = get_asset(from_asset, from_network)
        if not crypto or not crypto.enabled:
            raise ValidationFailedError(f"Asset {from_asset}/{from_network} is not supported")
        if amount_in < crypto.min_amount or amount_in > crypto.max_amount:
            raise ValidationFailedError(
                f"amount_in must be between {crypto.min_amount} and {crypto.max_amount} "
                f"{from_asset}"
            )
