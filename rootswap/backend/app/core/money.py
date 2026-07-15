"""Money helpers — all monetary math uses Decimal."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

MONEY_QUANT = Decimal("0.00000001")  # 8 dp crypto-safe
FIAT_QUANT = Decimal("0.01")


def D(value: Any) -> Decimal:
    """Coerce int/float/str/Decimal to Decimal without binary float traps when possible."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        raise ValueError("money value is None")
    if isinstance(value, float):
        # Prefer round-trip via str to avoid 0.1 artefacts when callers pass float.
        return Decimal(str(value))
    return Decimal(value)


def q8(value: Any) -> Decimal:
    return D(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def q2(value: Any) -> Decimal:
    return D(value).quantize(FIAT_QUANT, rounding=ROUND_HALF_UP)


def money_to_json(value: Any) -> float:
    """API JSON number (float) after Decimal quantization — for Mini App compatibility."""
    return float(q8(value))
