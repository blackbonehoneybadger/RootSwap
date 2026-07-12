from app.security.encryption import decrypt_value, encrypt_value
from app.security.masking import (
    mask_account,
    mask_card,
    mask_mapping,
    mask_phone,
    mask_wallet,
)


def test_encrypt_roundtrip():
    secret = "40817810000000054321"
    token = encrypt_value(secret)
    assert secret not in token
    assert decrypt_value(token) == secret


def test_mask_card():
    masked = mask_card("2200123456784321")
    assert masked == "2200 **** **** 4321"
    assert "1234567" not in masked


def test_mask_account():
    assert mask_account("40817810000000054321") == "****4321"


def test_mask_phone():
    masked = mask_phone("+79001234567")
    assert masked.endswith("67")
    assert "12345" not in masked


def test_mask_wallet():
    address = "4AdUndXHHZ6cfufTMvppY6JwXNouMBzSkbL"
    masked = mask_wallet(address)
    assert len(masked) < len(address)
    assert "..." in masked


def test_mask_mapping_masks_sensitive_keys():
    data = {
        "card_number": "2200123456784321",
        "wallet_address": "4AdUndXHHZ6cfufTMvppY6JwXNouMBzSkbL",
        "nested": {"account_number": "40817810000000054321"},
        "amount": "100",
    }
    masked = mask_mapping(data)
    assert "2200123456784321" not in str(masked)
    assert "40817810000000054321" not in str(masked)
    assert masked["amount"] == "100"
