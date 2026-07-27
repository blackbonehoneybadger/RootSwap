"""Strict wallet address validation for supported assets/networks.

- BTC: Base58Check (P2PKH `1...`, P2SH `3...`) with checksum, or Bech32/Bech32m (`bc1...`)
- XMR: standard (95 chars, prefix 4) / integrated (106 chars) / subaddress (95, prefix 8),
  Monero Base58 alphabet check
- USDT TRC20 (TRON): Base58Check, `T...`, 34 chars, version byte 0x41
- USDT ERC20: 0x + 40 hex chars with optional EIP-55 checksum verification
"""

import hashlib
import re

from app.core.errors import ValidationFailedError

B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
B58_INDEX = {c: i for i, c in enumerate(B58_ALPHABET)}

BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

# Format-validated pairs (sandbox tradeable + planned for future enablement).
SUPPORTED = {
    ("BTC", "BTC"),
    ("XMR", "XMR"),
    ("USDT", "TRC20"),
    ("USDT", "ERC20"),
    ("USDT", "SOL"),
    ("USDT", "TON"),
    ("USDT", "BSC"),
    ("USDC", "ERC20"),
    ("USDC", "SOL"),
    ("ETH", "ERC20"),
    ("SOL", "SOL"),
    ("TON", "TON"),
    ("XRP", "XRP"),
    ("DOGE", "DOGE"),
    ("DASH", "DASH"),
    ("BNB", "BSC"),
}

# Memo/tag required when the asset is enabled for trading.
MEMO_REQUIRED: set[tuple[str, str]] = {
    ("XRP", "XRP"),
    ("USDT", "TON"),
}


def _b58decode_check(value: str) -> bytes:
    num = 0
    for char in value:
        if char not in B58_INDEX:
            raise ValidationFailedError("invalid base58 character")
        num = num * 58 + B58_INDEX[char]
    raw = num.to_bytes((num.bit_length() + 7) // 8, "big")
    pad = len(value) - len(value.lstrip("1"))
    raw = b"\x00" * pad + raw
    if len(raw) < 5:
        raise ValidationFailedError("address too short")
    payload, checksum = raw[:-4], raw[-4:]
    digest = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if digest != checksum:
        raise ValidationFailedError("checksum mismatch")
    return payload


def _bech32_polymod(values: list[int]) -> int:
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= gen[i] if ((top >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _validate_bech32(address: str) -> None:
    addr = address.lower()
    if addr != address and address.upper() != address:
        raise ValidationFailedError("mixed-case bech32 address")
    pos = addr.rfind("1")
    if pos < 1 or pos + 7 > len(addr) or len(addr) > 90:
        raise ValidationFailedError("malformed bech32 address")
    hrp, data_part = addr[:pos], addr[pos + 1 :]
    if hrp != "bc":
        raise ValidationFailedError("not a bitcoin mainnet bech32 address")
    if any(c not in BECH32_CHARSET for c in data_part):
        raise ValidationFailedError("invalid bech32 character")
    data = [BECH32_CHARSET.index(c) for c in data_part]
    const = _bech32_polymod(_bech32_hrp_expand(hrp) + data)
    if const not in (1, 0x2BC830A3):  # bech32 / bech32m
        raise ValidationFailedError("bech32 checksum mismatch")


def validate_btc_address(address: str) -> None:
    if address.lower().startswith("bc1"):
        _validate_bech32(address)
        return
    if address[:1] in ("1", "3"):
        payload = _b58decode_check(address)
        if payload[0] not in (0x00, 0x05):
            raise ValidationFailedError("unknown BTC address version")
        return
    raise ValidationFailedError("unrecognized BTC address format")


XMR_B58 = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def validate_xmr_address(address: str) -> None:
    if len(address) not in (95, 106):
        raise ValidationFailedError("XMR address must be 95 or 106 characters")
    if address[0] not in ("4", "8"):
        raise ValidationFailedError("XMR mainnet address must start with 4 or 8")
    if any(c not in XMR_B58 for c in address):
        raise ValidationFailedError("invalid XMR base58 character")


def validate_tron_address(address: str) -> None:
    if not address.startswith("T") or len(address) != 34:
        raise ValidationFailedError("TRON address must start with T and be 34 chars")
    payload = _b58decode_check(address)
    if payload[0] != 0x41:
        raise ValidationFailedError("wrong TRON address version byte")


def validate_eth_address(address: str) -> None:
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
        raise ValidationFailedError("ETH address must be 0x + 40 hex chars")
    body = address[2:]
    if body != body.lower() and body != body.upper():
        # verify EIP-55 checksum
        try:
            from Crypto.Hash import keccak  # type: ignore  # optional  # noqa: F401
        except ImportError:
            return  # mixed case but no keccak available: accept hex-valid address
        digest = keccak.new(digest_bits=256, data=body.lower().encode()).hexdigest()
        for i, char in enumerate(body):
            if char.isalpha():
                expected_upper = int(digest[i], 16) >= 8
                if char.isupper() != expected_upper:
                    raise ValidationFailedError("EIP-55 checksum mismatch")


SOL_B58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
TON_ADDR = re.compile(r"^(EQ|UQ|0:)[A-Za-z0-9_-]{46,}$")
XRP_ADDR = re.compile(r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")
DOGE_ADDR = re.compile(r"^D[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}$")
DASH_ADDR = re.compile(r"^X[1-9A-HJ-NP-Za-km-z]{33}$")


def validate_sol_address(address: str) -> None:
    if not SOL_B58.fullmatch(address):
        raise ValidationFailedError("invalid Solana address format")


def validate_ton_address(address: str) -> None:
    if not TON_ADDR.fullmatch(address):
        raise ValidationFailedError("invalid TON address format")


def validate_xrp_address(address: str) -> None:
    if not XRP_ADDR.fullmatch(address):
        raise ValidationFailedError("invalid XRP address format")


def validate_doge_address(address: str) -> None:
    if not DOGE_ADDR.fullmatch(address):
        raise ValidationFailedError("invalid DOGE address format")


def validate_dash_address(address: str) -> None:
    if not DASH_ADDR.fullmatch(address):
        raise ValidationFailedError("invalid DASH address format")


def validate_wallet_address(
    asset: str,
    network: str | None,
    address: str,
    *,
    memo: str | None = None,
    require_memo_if_needed: bool = False,
) -> None:
    """Raise ValidationFailedError when the address is not valid for asset/network.

    Checksum validation is applied for BTC/TRON/ETH where implemented.
    Other networks use strict format validation until live partners land.
    """
    asset = asset.upper()
    network = (network or asset).upper()
    if (asset, network) not in SUPPORTED:
        raise ValidationFailedError(
            f"unsupported asset/network combination: {asset}/{network}"
        )
    address = address.strip()
    if not address:
        raise ValidationFailedError("address is empty")
    if asset == "BTC":
        validate_btc_address(address)
    elif asset == "XMR":
        validate_xmr_address(address)
    elif asset == "USDT" and network == "TRC20":
        validate_tron_address(address)
    elif network in ("ERC20", "BSC") and asset in ("USDT", "USDC", "ETH", "BNB"):
        validate_eth_address(address)
    elif network == "SOL" and asset in ("USDT", "USDC", "SOL"):
        validate_sol_address(address)
    elif network == "TON" and asset in ("TON", "USDT"):
        validate_ton_address(address)
    elif asset == "XRP" and network == "XRP":
        validate_xrp_address(address)
    elif asset == "DOGE" and network == "DOGE":
        validate_doge_address(address)
    elif asset == "DASH" and network == "DASH":
        validate_dash_address(address)
    else:
        raise ValidationFailedError(f"unsupported wallet validation for {asset}/{network}")

    if require_memo_if_needed and (asset, network) in MEMO_REQUIRED:
        if memo is None or not str(memo).strip():
            raise ValidationFailedError("memo/tag required for this network")
