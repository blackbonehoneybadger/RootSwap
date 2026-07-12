"""Deterministic mock fiat partner.

All rates, fees and addresses are synthetic. No real money moves anywhere.
Failure scenarios are controlled from tests via `set_scenario()` and are fully
deterministic (no randomness, no wall-clock dependence in decisions).
"""

import hashlib
import hmac
from decimal import Decimal

from app.core.config import get_settings
from app.core.enums import OrderDirection, PaymentMethod, QuoteSourceType
from app.partners.base import (
    FiatPartnerAdapter,
    PartnerError,
    PartnerLimits,
    PartnerOrderResult,
    PartnerQuote,
    Route,
)

RUB = "RUB"

# 1 unit of crypto costs this many RUB (synthetic, deterministic)
CRYPTO_RATES_RUB = {
    "USDT": Decimal("80"),
    "BTC": Decimal("8000000"),
    "XMR": Decimal("20000"),
}

NETWORK_FEE_RUB = {
    "USDT": Decimal("120"),
    "BTC": Decimal("300"),
    "XMR": Decimal("20"),
}

ASSET_NETWORKS = {"USDT": "TRC20", "BTC": "BTC", "XMR": "XMR"}

MOCK_BANKS = ["Sber", "Tinkoff", "Alfa", "Raiffeisen", "AnyBank"]

MOCK_DEPOSIT_ADDRESSES = {
    "USDT": "TQmockDepositUSDTtrc20xxxxxxxxxxx01",
    "BTC": "bc1qmockdepositbtc000000000000000000000001",
    "XMR": "4mockDepositXMR" + "a" * 80,
}

SCENARIOS = {
    "success",
    "quote_failure",
    "fail_before_order",
    "insufficient_reserve",
    "expired_payment",
    "slow_processing",
    "refund",
    "dispute",
}


def _mk_routes() -> list[Route]:
    routes = []
    for asset, network in ASSET_NETWORKS.items():
        routes.append(Route(OrderDirection.BUY, RUB, None, asset, network))
        routes.append(Route(OrderDirection.SELL, asset, network, RUB, None))
    return routes


class MockFiatPartnerAdapter(FiatPartnerAdapter):
    quote_source_type = QuoteSourceType.MOCK
    environment = "mock"

    def __init__(
        self,
        code: str = "mock_fiat_alpha",
        name: str = "Mock Fiat Alpha",
        fee_percent: Decimal = Decimal("0.4"),
        latency_score_minutes: int = 12,
    ) -> None:
        self.code = code
        self.name = name
        self.fee_percent = fee_percent
        self.latency_score_minutes = latency_score_minutes
        self._scenario = "success"
        self._orders: dict[str, dict] = {}
        self._order_seq = 0
        self._healthy = True

    # --- test controls -----------------------------------------------------
    def set_scenario(self, scenario: str) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario}")
        self._scenario = scenario

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = healthy

    @property
    def scenario(self) -> str:
        return self._scenario

    # --- adapter API -------------------------------------------------------
    def supported_routes(self) -> list[Route]:
        return _mk_routes()

    async def get_fiat_quote(self, route: Route, amount_in: Decimal) -> PartnerQuote:
        if not self._healthy or self._scenario == "quote_failure":
            raise PartnerError(f"{self.code}: quote endpoint unavailable (mock)")
        reserve_available = self._scenario != "insufficient_reserve"

        partner_fee = (amount_in * self.fee_percent / Decimal("100")).quantize(Decimal("0.01")) \
            if route.from_asset == RUB else Decimal("0")

        if route.direction == OrderDirection.BUY:
            asset = route.to_asset
            rate = CRYPTO_RATES_RUB[asset]
            network_fee = NETWORK_FEE_RUB[asset]
            net_rub = amount_in - partner_fee - network_fee
            if net_rub <= 0:
                raise PartnerError("amount too small after fees")
            amount_out = (net_rub / rate).quantize(Decimal("0.00000001"))
            exchange_rate = rate
        else:
            asset = route.from_asset
            rate = CRYPTO_RATES_RUB[asset]
            network_fee = NETWORK_FEE_RUB[asset]
            gross_rub = amount_in * rate
            partner_fee = (gross_rub * self.fee_percent / Decimal("100")).quantize(Decimal("0.01"))
            amount_out = (gross_rub - partner_fee - network_fee).quantize(Decimal("0.01"))
            if amount_out <= 0:
                raise PartnerError("amount too small after fees")
            exchange_rate = rate

        return PartnerQuote(
            partner_code=self.code,
            direction=route.direction,
            from_asset=route.from_asset,
            from_network=route.from_network,
            to_asset=route.to_asset,
            to_network=route.to_network,
            amount_in=amount_in,
            amount_out=amount_out,
            exchange_rate=exchange_rate,
            partner_fee=partner_fee,
            network_fee=network_fee,
            estimated_time_minutes=self.latency_score_minutes,
            kyc_required=False,
            reserve_available=reserve_available,
            raw={"mock": True, "scenario": self._scenario, "partner": self.code},
        )

    async def create_fiat_order(
        self,
        route: Route,
        amount_in: Decimal,
        client_order_id: str,
        payment_method: str | None = None,
        bank: str | None = None,
        payout_details: dict | None = None,
        wallet_address: str | None = None,
    ) -> PartnerOrderResult:
        if not self._healthy or self._scenario == "fail_before_order":
            raise PartnerError(f"{self.code}: order creation failed (mock)")
        self._order_seq += 1
        partner_order_id = f"{self.code}-ord-{self._order_seq:06d}"
        record = {
            "route": route,
            "amount_in": amount_in,
            "client_order_id": client_order_id,
            "status": "awaiting_payment",
            "scenario": self._scenario,
        }
        self._orders[partner_order_id] = record

        if route.direction == OrderDirection.BUY:
            bank = bank if bank in MOCK_BANKS else "AnyBank"
            method = payment_method or PaymentMethod.SBP.value
            instructions = {
                "payment_method": method,
                "bank_name": bank,
                "recipient_name": "Ivan Mockov",
                "account_number": "40817810000000054321",
                "card_number": "2200123456784321" if method == PaymentMethod.CARD_TRANSFER.value else None,
                "sbp_phone": "+79001234567" if method == PaymentMethod.SBP.value else None,
                "amount": str(amount_in),
                "currency": RUB,
                "payment_comment": f"RS-{client_order_id[:8].upper()}",
            }
            return PartnerOrderResult(
                partner_order_id=partner_order_id,
                status="awaiting_payment",
                payment_instructions=instructions,
                raw={"mock": True},
            )

        asset = route.from_asset
        return PartnerOrderResult(
            partner_order_id=partner_order_id,
            status="awaiting_payment",
            deposit_address=MOCK_DEPOSIT_ADDRESSES[asset],
            deposit_network=route.from_network,
            raw={"mock": True},
        )

    async def get_payment_instructions(self, partner_order_id: str) -> dict:
        order = self._orders.get(partner_order_id)
        if not order:
            raise PartnerError("unknown partner order")
        return {"partner_order_id": partner_order_id, "status": order["status"]}

    async def get_order_status(self, partner_order_id: str) -> str:
        order = self._orders.get(partner_order_id)
        if not order:
            raise PartnerError("unknown partner order")
        return order["status"]

    def set_order_status(self, partner_order_id: str, status: str) -> None:
        """Test helper: simulate partner-side progress for polling fallback."""
        if partner_order_id in self._orders:
            self._orders[partner_order_id]["status"] = status

    async def cancel_order(self, partner_order_id: str) -> bool:
        order = self._orders.get(partner_order_id)
        if not order:
            return False
        order["status"] = "cancelled"
        return True

    async def request_refund(self, partner_order_id: str, reason: str) -> str:
        order = self._orders.get(partner_order_id)
        if not order:
            raise PartnerError("unknown partner order")
        order["status"] = "refund_processing"
        return f"refund-{partner_order_id}"

    async def get_limits(self, route: Route) -> PartnerLimits:
        if route.from_asset == RUB:
            return PartnerLimits(Decimal("1000"), Decimal("300000"), RUB)
        return PartnerLimits(Decimal("0.0001"), Decimal("100"), route.from_asset)

    async def get_supported_banks(self) -> list[str]:
        return list(MOCK_BANKS)

    async def get_supported_payment_methods(self) -> list[str]:
        return [m.value for m in PaymentMethod]

    def verify_webhook(self, payload: bytes, signature: str, timestamp: str) -> bool:
        secret = get_settings().partner_webhook_secret or "mock-webhook-secret"
        expected = hmac.new(
            secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    async def health_check(self) -> bool:
        return self._healthy


def sign_mock_webhook(payload: bytes, timestamp: str, secret: str | None = None) -> str:
    """Helper used by tests to produce a valid mock partner webhook signature."""
    secret = secret or (get_settings().partner_webhook_secret or "mock-webhook-secret")
    return hmac.new(secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
