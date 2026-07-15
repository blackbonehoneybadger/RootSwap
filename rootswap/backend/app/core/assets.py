"""Canonical asset registry for demo MVP.

An asset/route is "supported" only when listed here as enabled AND
implemented by at least one partner adapter (see mock_fiat SUPPORTED_ROUTES).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import OrderDirection
from app.core.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class AssetSpec:
    symbol: str
    name: str
    network: str | None
    decimals: int
    enabled: bool
    min_amount: float
    max_amount: float
    status: str  # "supported" | "planned" | "disabled"


# Fiat used as source/target alongside crypto.
ASSETS: dict[tuple[str, str | None], AssetSpec] = {
    ("RUB", None): AssetSpec("RUB", "Russian Ruble", None, 2, True, 1000.0, 500_000.0, "supported"),
    ("USDT", "TRC20"): AssetSpec(
        "USDT", "Tether USD", "TRC20", 6, True, 10.0, 20_000.0, "supported"
    ),
    ("BTC", "BTC"): AssetSpec("BTC", "Bitcoin", "BTC", 8, True, 0.0001, 2.0, "supported"),
    ("XMR", "XMR"): AssetSpec(
        "XMR", "Monero", "XMR", 12, True, 0.01, 200.0, "supported"
    ),
    # Explicitly not enabled for this MVP (no adapter route).
    ("USDT", "ERC20"): AssetSpec(
        "USDT", "Tether USD", "ERC20", 6, False, 10.0, 20_000.0, "planned"
    ),
    ("SOL", "SOL"): AssetSpec("SOL", "Solana", "SOL", 9, False, 0.1, 5_000.0, "planned"),
}

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


def list_supported_assets() -> list[AssetSpec]:
    return [a for a in ASSETS.values() if a.enabled and a.status == "supported"]


def validate_route(
    direction: OrderDirection,
    from_asset: str,
    from_network: str | None,
    to_asset: str,
    to_network: str | None,
    amount_in: float,
) -> None:
    route = (
        direction,
        from_asset.upper(),
        from_network.upper() if from_network else None,
        to_asset.upper(),
        to_network.upper() if to_network else None,
    )
    if route not in SUPPORTED_ROUTES:
        raise ValidationError(
            f"Unsupported route: {direction.value} "
            f"{from_asset}/{from_network} → {to_asset}/{to_network}"
        )

    # Amount limits apply to the fiat side for BUY, crypto side for SELL.
    if direction == OrderDirection.BUY:
        fiat = get_asset("RUB", None)
        assert fiat is not None
        if amount_in < fiat.min_amount or amount_in > fiat.max_amount:
            raise ValidationError(
                f"amount_in must be between {fiat.min_amount} and {fiat.max_amount} RUB"
            )
    else:
        crypto = get_asset(from_asset, from_network)
        if not crypto or not crypto.enabled:
            raise ValidationError(f"Asset {from_asset}/{from_network} is not supported")
        if amount_in < crypto.min_amount or amount_in > crypto.max_amount:
            raise ValidationError(
                f"amount_in must be between {crypto.min_amount} and {crypto.max_amount} "
                f"{from_asset}"
            )
