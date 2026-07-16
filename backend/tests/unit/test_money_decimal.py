"""Decimal money invariants — no float drift in financial math."""

from decimal import ROUND_HALF_UP, Decimal

from app.services.fees import compute_service_fee, compute_total_fee


def test_point_one_plus_point_two():
    total = Decimal("0.1") + Decimal("0.2")
    assert total == Decimal("0.3")
    assert str(total) == "0.3"


def test_fee_rounding_stable():
    fee = compute_service_fee(Decimal("10000"), Decimal("0.9"))
    assert fee == Decimal("90.00") or fee == Decimal("90")
    # re-serialize
    assert Decimal(str(fee)) == fee


def test_large_amount():
    amount = Decimal("99999999.12345678")
    fee = compute_service_fee(amount, Decimal("0.9"))
    assert isinstance(fee, Decimal)
    assert fee == (amount * Decimal("0.9") / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def test_eight_decimal_places_preserved():
    amount_out = Decimal("0.12345678")
    assert format(amount_out, "f") == "0.12345678"
    assert Decimal(format(amount_out, "f")) == amount_out


def test_total_fee_components():
    total = compute_total_fee(Decimal("90"), Decimal("40"), Decimal("120"))
    assert total == Decimal("250")
