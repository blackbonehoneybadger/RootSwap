"""Masking helpers: sensitive values must never appear in full in logs or API
responses other than the dedicated payment-instructions endpoint (masked there too).
"""

import re

SENSITIVE_KEYS = {
    "card_number",
    "account_number",
    "phone",
    "sbp_phone",
    "recipient_name",
    "wallet_address",
    "address",
    "payout_details",
    "initdata",
    "init_data",
    "token",
    "secret",
    "authorization",
    "signature",
}


def mask_card(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 8:
        return "*" * len(digits)
    return f"{digits[:4]} **** **** {digits[-4:]}"


def mask_account(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "*" * len(digits)
    return f"****{digits[-4:]}"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "*" * len(digits)
    return f"+{digits[0]}*******{digits[-2:]}"


def mask_name(value: str) -> str:
    parts = value.split()
    return " ".join(p[0] + "." if p else "" for p in parts)


def mask_wallet(value: str) -> str:
    if len(value) <= 12:
        return value[:3] + "..." + value[-2:]
    return f"{value[:6]}...{value[-6:]}"


def mask_generic(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def mask_mapping(data: dict) -> dict:
    """Recursively mask values whose keys look sensitive. Used before logging."""
    out: dict = {}
    for key, value in data.items():
        lowered = str(key).lower()
        if isinstance(value, dict):
            out[key] = mask_mapping(value)
        elif any(s in lowered for s in SENSITIVE_KEYS) and isinstance(value, str):
            out[key] = mask_generic(value)
        else:
            out[key] = value
    return out
