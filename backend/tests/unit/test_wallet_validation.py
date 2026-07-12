import pytest

from app.core.errors import ValidationFailedError
from app.services.wallet_validation import validate_wallet_address
from tests.conftest import VALID_BTC_BECH32, VALID_BTC_LEGACY, VALID_TRON, VALID_XMR


def test_valid_btc_legacy():
    validate_wallet_address("BTC", "BTC", VALID_BTC_LEGACY)


def test_valid_btc_bech32():
    validate_wallet_address("BTC", "BTC", VALID_BTC_BECH32)


def test_btc_bad_checksum():
    broken = VALID_BTC_LEGACY[:-1] + ("a" if VALID_BTC_LEGACY[-1] != "a" else "b")
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("BTC", "BTC", broken)


def test_btc_bech32_bad_checksum():
    broken = VALID_BTC_BECH32[:-1] + ("q" if VALID_BTC_BECH32[-1] != "q" else "p")
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("BTC", "BTC", broken)


def test_valid_xmr():
    validate_wallet_address("XMR", "XMR", VALID_XMR)


def test_xmr_wrong_length():
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("XMR", "XMR", VALID_XMR[:-1])


def test_xmr_wrong_prefix():
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("XMR", "XMR", "9" + VALID_XMR[1:])


def test_xmr_invalid_charset():
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("XMR", "XMR", VALID_XMR[:-1] + "0")  # 0 not in base58


def test_valid_tron():
    validate_wallet_address("USDT", "TRC20", VALID_TRON)


def test_tron_bad_checksum():
    broken = VALID_TRON[:-1] + ("a" if VALID_TRON[-1] != "a" else "b")
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("USDT", "TRC20", broken)


def test_incompatible_network_rejected():
    # BTC address offered for USDT TRC20
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("USDT", "TRC20", VALID_BTC_LEGACY)


def test_unsupported_combination_rejected():
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("BTC", "TRC20", VALID_BTC_LEGACY)


def test_erc20_hex_address():
    validate_wallet_address("USDT", "ERC20", "0x" + "ab" * 20)
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("USDT", "ERC20", "0x" + "zz" * 20)


def test_empty_address_rejected():
    with pytest.raises(ValidationFailedError):
        validate_wallet_address("BTC", "BTC", "   ")
