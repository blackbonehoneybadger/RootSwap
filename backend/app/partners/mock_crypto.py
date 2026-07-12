"""Deterministic mock crypto partner (crypto-side interface reference).

Registered but disabled by default: the six launch routes are fiat-legged and
served by mock fiat partners. This adapter exists so the crypto contract is
implemented, tested and ready for a real crypto partner integration.
"""

import hashlib
import hmac
from decimal import Decimal

from app.core.config import get_settings
from app.core.enums import OrderDirection, QuoteSourceType
from app.partners.base import (
    CryptoPartnerAdapter,
    PartnerError,
    PartnerOrderResult,
    PartnerQuote,
    Route,
)
from app.partners.mock_fiat import (
    ASSET_NETWORKS,
    CRYPTO_RATES_RUB,
    MOCK_DEPOSIT_ADDRESSES,
    NETWORK_FEE_RUB,
)


class MockCryptoPartnerAdapter(CryptoPartnerAdapter):
    quote_source_type = QuoteSourceType.MOCK
    environment = "mock"

    def __init__(self, code: str = "mock_crypto", name: str = "Mock Crypto") -> None:
        self.code = code
        self.name = name
        self._orders: dict[str, dict] = {}
        self._seq = 0
        self._healthy = True

    def supported_routes(self) -> list[Route]:
        return [
            Route(OrderDirection.SELL, asset, network, "RUB", None)
            for asset, network in ASSET_NETWORKS.items()
        ]

    async def get_quote(self, route: Route, amount_in: Decimal) -> PartnerQuote:
        if not self._healthy:
            raise PartnerError(f"{self.code}: unavailable")
        rate = CRYPTO_RATES_RUB[route.from_asset]
        network_fee = NETWORK_FEE_RUB[route.from_asset]
        partner_fee = (amount_in * rate * Decimal("0.005")).quantize(Decimal("0.01"))
        amount_out = (amount_in * rate - partner_fee - network_fee).quantize(Decimal("0.01"))
        if amount_out <= 0:
            raise PartnerError("amount too small after fees")
        return PartnerQuote(
            partner_code=self.code,
            direction=route.direction,
            from_asset=route.from_asset,
            from_network=route.from_network,
            to_asset=route.to_asset,
            to_network=route.to_network,
            amount_in=amount_in,
            amount_out=amount_out,
            exchange_rate=rate,
            partner_fee=partner_fee,
            network_fee=network_fee,
            estimated_time_minutes=25,
            kyc_required=False,
            reserve_available=True,
            raw={"mock": True},
        )

    async def create_order(
        self,
        route: Route,
        amount_in: Decimal,
        client_order_id: str,
        wallet_address: str | None = None,
    ) -> PartnerOrderResult:
        if not self._healthy:
            raise PartnerError(f"{self.code}: unavailable")
        self._seq += 1
        partner_order_id = f"{self.code}-ord-{self._seq:06d}"
        self._orders[partner_order_id] = {"status": "awaiting_payment"}
        return PartnerOrderResult(
            partner_order_id=partner_order_id,
            status="awaiting_payment",
            deposit_address=MOCK_DEPOSIT_ADDRESSES[route.from_asset],
            deposit_network=route.from_network,
            raw={"mock": True},
        )

    async def get_order_status(self, partner_order_id: str) -> str:
        order = self._orders.get(partner_order_id)
        if not order:
            raise PartnerError("unknown partner order")
        return order["status"]

    async def cancel_order(self, partner_order_id: str) -> bool:
        order = self._orders.get(partner_order_id)
        if not order:
            return False
        order["status"] = "cancelled"
        return True

    async def get_supported_currencies(self) -> list[dict]:
        return [
            {"asset": asset, "network": network}
            for asset, network in ASSET_NETWORKS.items()
        ]

    def verify_webhook(self, payload: bytes, signature: str, timestamp: str) -> bool:
        secret = get_settings().partner_webhook_secret or "mock-webhook-secret"
        expected = hmac.new(
            secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    async def health_check(self) -> bool:
        return self._healthy
