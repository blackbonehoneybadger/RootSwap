import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.enums import OrderDirection, OrderStatus
from app.partners.base import (
    FiatPartnerAdapter,
    OrderRequest,
    OrderResult,
    PartnerOrderStatus,
    PaymentInstructionsResult,
    QuoteRequest,
    QuoteResult,
)

MOCK_RATES = {
    ("RUB", "USDT"): 0.0105,
    ("RUB", "BTC"): 0.000000095,
    ("RUB", "XMR"): 0.000045,
    ("USDT", "RUB"): 95.0,
    ("BTC", "RUB"): 10500000.0,
    ("XMR", "RUB"): 22000.0,
}

SUPPORTED_ROUTES = {
    OrderDirection.BUY: [
        ("RUB", None, "USDT", "TRC20"),
        ("RUB", None, "BTC", "BTC"),
        ("RUB", None, "XMR", "XMR"),
    ],
    OrderDirection.SELL: [
        ("USDT", "TRC20", "RUB", None),
        ("BTC", "BTC", "RUB", None),
        ("XMR", "XMR", "RUB", None),
    ],
}

BANKS = ["Sber", "Tinkoff", "Alfa", "Raiffeisen", "AnyBank"]
PAYMENT_METHODS = ["SBP", "bank_transfer", "card_transfer"]

PARTNER_STATUS_MAP = {
    "awaiting_payment": OrderStatus.AWAITING_PAYMENT,
    "payment_detected": OrderStatus.PAYMENT_DETECTED,
    "payment_confirming": OrderStatus.PAYMENT_CONFIRMING,
    "processing": OrderStatus.PROCESSING,
    "payout_sent": OrderStatus.PAYOUT_SENT,
    "completed": OrderStatus.COMPLETED,
    "expired": OrderStatus.EXPIRED,
    "failed": OrderStatus.FAILED,
    "disputed": OrderStatus.DISPUTED,
    "refund_requested": OrderStatus.REFUND_REQUESTED,
    "refund_processing": OrderStatus.REFUND_PROCESSING,
    "refunded": OrderStatus.REFUNDED,
    "refund_failed": OrderStatus.REFUND_FAILED,
    "cancelled": OrderStatus.CANCELLED,
}


class MockFiatPartnerAdapter(FiatPartnerAdapter):
    partner_code = "mock_fiat"
    webhook_secret = "mock-webhook-secret"

    def __init__(self, partner_code: str | None = None) -> None:
        if partner_code:
            self.partner_code = partner_code
        self._orders: dict[str, dict[str, Any]] = {}
        self._scenario_overrides: dict[str, str] = {}

    def set_scenario(self, scenario: str | None) -> None:
        self._current_scenario = scenario

    def _get_scenario(self, request: QuoteRequest | OrderRequest | None = None) -> str:
        if request and getattr(request, "scenario", None):
            return request.scenario  # type: ignore[return-value]
        return getattr(self, "_current_scenario", "success")

    def _rate(self, from_asset: str, to_asset: str) -> float:
        return MOCK_RATES.get((from_asset, to_asset), 1.0)

    def _partner_order_id(self, seed: str) -> str:
        return f"MOCK-{hashlib.sha256(seed.encode()).hexdigest()[:12].upper()}"

    async def get_fiat_quote(self, request: QuoteRequest) -> QuoteResult:
        scenario = self._get_scenario(request)
        if scenario == "partner_failure":
            raise RuntimeError("Mock partner failure before order")
        if scenario == "insufficient_reserve":
            reserve = 0.0
        else:
            reserve = 1_000_000.0

        if request.direction == OrderDirection.BUY.value:
            rate = self._rate("RUB", request.to_asset)
            amount_out = request.amount_in * rate
            network_fee = 0.0001 if request.to_asset == "BTC" else 0.01
        else:
            rate = self._rate(request.from_asset, "RUB")
            amount_out = request.amount_in * rate
            network_fee = 50.0

        partner_fee = request.amount_in * 0.005
        if scenario == "slow_processing":
            await asyncio.sleep(0.1)

        return QuoteResult(
            partner_code=self.partner_code,
            partner_order_id=None,
            amount_out=round(amount_out, 8),
            exchange_rate=rate,
            partner_fee=round(partner_fee, 8),
            network_fee=network_fee,
            estimated_time_seconds=600 if scenario != "slow_processing" else 3600,
            kyc_required=False,
            reserve_available=reserve,
            raw_response={"scenario": scenario, "mock": True},
        )

    async def create_fiat_order(self, request: OrderRequest) -> OrderResult:
        scenario = self._get_scenario(request)
        if scenario == "partner_failure":
            raise RuntimeError("Mock partner failure before order")

        partner_order_id = self._partner_order_id(request.idempotency_key)
        status = "awaiting_payment"
        deposit_address = None
        payment_instructions = None

        if scenario == "expired_payment":
            status = "expired"

        order_data = {
            "partner_order_id": partner_order_id,
            "status": status,
            "scenario": scenario,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._orders[partner_order_id] = order_data

        return OrderResult(
            partner_order_id=partner_order_id,
            status=status,
            deposit_address=deposit_address,
            payment_instructions=payment_instructions,
            raw_response=order_data,
        )

    async def get_payment_instructions(self, partner_order_id: str) -> PaymentInstructionsResult:
        order = self._orders.get(partner_order_id, {})
        scenario = order.get("scenario", "success")
        expires = datetime.now(UTC) + timedelta(minutes=15)
        if scenario == "expired_payment":
            expires = datetime.now(UTC) - timedelta(minutes=1)

        return PaymentInstructionsResult(
            payment_method="SBP",
            bank_name="Sber",
            recipient_name="Mock Recipient",
            account_number="40817810099910004312",
            card_number="5536910000001234",
            sbp_phone="+79001234567",
            deposit_address="T" + "A" * 33,
            amount=10000.0,
            currency="RUB",
            payment_comment=f"PAY-{partner_order_id[-8:]}",
            expires_at=expires,
        )

    async def get_order_status(self, partner_order_id: str) -> PartnerOrderStatus:
        order = self._orders.get(partner_order_id, {"status": "processing"})
        return PartnerOrderStatus(
            partner_order_id=partner_order_id,
            status=order.get("status", "processing"),
            message="Mock status",
            raw_response=order,
        )

    def simulate_status(self, partner_order_id: str, status: str) -> None:
        if partner_order_id not in self._orders:
            self._orders[partner_order_id] = {"partner_order_id": partner_order_id}
        self._orders[partner_order_id]["status"] = status

    async def cancel_order(self, partner_order_id: str) -> PartnerOrderStatus:
        self.simulate_status(partner_order_id, "cancelled")
        return await self.get_order_status(partner_order_id)

    async def request_refund(self, partner_order_id: str) -> PartnerOrderStatus:
        self.simulate_status(partner_order_id, "refund_processing")
        return await self.get_order_status(partner_order_id)

    async def get_limits(self) -> dict:
        return {"min": 1000, "max": 500000, "currency": "RUB"}

    async def get_supported_banks(self) -> list[str]:
        return BANKS

    async def get_supported_payment_methods(self) -> list[str]:
        return PAYMENT_METHODS

    async def verify_webhook(self, payload: bytes, headers: dict[str, str]) -> tuple[bool, dict]:
        def h(name: str) -> str | None:
            for k, v in headers.items():
                if k.lower() == name.lower():
                    return v
            return None

        signature = h("X-Mock-Signature") or ""
        timestamp = h("X-Mock-Timestamp") or ""
        if h("X-Mock-Invalid") == "true":
            return False, {}
        if not signature or not timestamp:
            return False, {}
        expected = hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return False, {}
        try:
            ts = int(timestamp)
            if abs(datetime.now(UTC).timestamp() - ts) > 300:
                return False, {}
        except ValueError:
            return False, {}
        data = json.loads(payload)
        return True, data

    def build_webhook_payload(
        self,
        partner_order_id: str,
        status: str,
        external_event_id: str | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        payload = {
            "event_id": external_event_id or f"evt-{partner_order_id}-{status}",
            "partner_order_id": partner_order_id,
            "status": status,
            "timestamp": int(datetime.now(UTC).timestamp()),
        }
        body = json.dumps(payload).encode()
        signature = hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        headers = {
            "X-Mock-Signature": signature,
            "X-Mock-Timestamp": str(payload["timestamp"]),
        }
        return body, headers

    async def health_check(self) -> bool:
        return True

    def supports_route(
        self,
        direction: OrderDirection,
        from_asset: str,
        from_network: str | None,
        to_asset: str,
        to_network: str | None,
    ) -> bool:
        routes = SUPPORTED_ROUTES.get(direction, [])
        return (from_asset, from_network, to_asset, to_network) in routes
