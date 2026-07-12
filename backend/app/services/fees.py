from decimal import ROUND_HALF_UP, Decimal

from app.core.config import get_settings


def compute_service_fee(amount_in_fiat: Decimal, percent: Decimal | None = None) -> Decimal:
    """Service fee in the fiat leg currency (RUB). Never negative."""
    if percent is None:
        percent = Decimal(get_settings().service_fee_percent)
    if amount_in_fiat < 0:
        raise ValueError("amount must be non-negative")
    fee = amount_in_fiat * percent / Decimal("100")
    return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_total_fee(service_fee: Decimal, partner_fee: Decimal, network_fee: Decimal) -> Decimal:
    return service_fee + partner_fee + network_fee
