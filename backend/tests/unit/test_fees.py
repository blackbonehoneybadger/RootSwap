from decimal import Decimal

import pytest

from app.services.fees import compute_service_fee, compute_total_fee


def test_service_fee_default_percent():
    assert compute_service_fee(Decimal("10000"), Decimal("0.9")) == Decimal("90.00")


def test_service_fee_rounding():
    assert compute_service_fee(Decimal("333"), Decimal("0.9")) == Decimal("3.00")
    assert compute_service_fee(Decimal("334"), Decimal("0.9")) == Decimal("3.01")


def test_service_fee_zero_amount():
    assert compute_service_fee(Decimal("0"), Decimal("0.9")) == Decimal("0.00")


def test_service_fee_negative_amount_rejected():
    with pytest.raises(ValueError):
        compute_service_fee(Decimal("-1"), Decimal("0.9"))


def test_total_fee_sum():
    assert compute_total_fee(Decimal("90"), Decimal("40"), Decimal("20")) == Decimal("150")
