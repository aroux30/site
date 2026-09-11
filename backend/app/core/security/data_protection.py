"""Field-level data protection, masking, and redaction for sensitive customer and financial PII.

Conforms to Evidence-Gated Production Hardening Master Task v3.0 Phase 10:
- Phone number masking
- National code / ID masking
- Email redaction
- IBAN and Card PAN masking
- Dictionary-level recursive audit redaction
"""

from __future__ import annotations

import re
from typing import Any, Mapping


def mask_phone(phone: str | None) -> str:
    """Mask an Iranian mobile phone number.

    Example:
        '09123456789' -> '0912***6789'
        '+989123456789' -> '+98912***6789'
    """
    if not phone:
        return ""
    clean = phone.strip()
    if len(clean) >= 10:
        prefix_len = 4 if clean.startswith("09") else (6 if clean.startswith("+98") else 3)
        suffix_len = 4
        if len(clean) > prefix_len + suffix_len:
            return f"{clean[:prefix_len]}***{clean[-suffix_len:]}"
    return f"{clean[:2]}***{clean[-2:]}" if len(clean) > 4 else "***"


def mask_national_code(code: str | None) -> str:
    """Mask a 10-digit Iranian National Code (کد ملی).

    Example:
        '1234567890' -> '******7890'
    """
    if not code:
        return ""
    clean = code.strip()
    if len(clean) >= 4:
        return f"{'*' * (len(clean) - 4)}{clean[-4:]}"
    return "****"


def mask_email(email: str | None) -> str:
    """Mask an email address while preserving domain context.

    Example:
        'johndoe@example.com' -> 'j***e@example.com'
        'a@b.com' -> '*@b.com'
    """
    if not email or "@" not in email:
        return ""
    local_part, domain = email.split("@", 1)
    if len(local_part) <= 2:
        masked_local = f"{local_part[0]}*" if local_part else "*"
    else:
        masked_local = f"{local_part[0]}***{local_part[-1]}"
    return f"{masked_local}@{domain}"


def mask_iban(iban: str | None) -> str:
    """Mask an Iranian IBAN (Sheba number).

    Example:
        'IR120120000000001234567890' -> 'IR12******************7890'
    """
    if not iban:
        return ""
    clean = iban.strip().replace(" ", "").upper()
    if len(clean) >= 8:
        return f"{clean[:4]}{'*' * (len(clean) - 8)}{clean[-4:]}"
    return "****"


def mask_card_pan(pan: str | None) -> str:
    """Mask a 16-digit debit/credit card number.

    Example:
        '6037991812345678' -> '6037-****-****-5678'
    """
    if not pan:
        return ""
    digits = re.sub(r"\D", "", pan)
    if len(digits) == 16:
        return f"{digits[:4]}-****-****-{digits[-4:]}"
    if len(digits) > 8:
        return f"{digits[:4]}{'*' * (len(digits) - 8)}{digits[-4:]}"
    return "****"


# Default sensitive keys to scrub from logs or customer payloads
DEFAULT_SENSITIVE_KEYS: frozenset[str] = frozenset({
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "jwt_secret",
    "cvv",
    "cvv2",
    "pin",
    "private_key",
    "api_key",
    "national_code",
    "card_number",
    "pan",
})


def redact_sensitive_payload(
    data: Any,
    sensitive_keys: frozenset[str] = DEFAULT_SENSITIVE_KEYS,
) -> Any:
    """Recursively scrub sensitive keys from dictionaries or lists for safe logging."""
    if isinstance(data, Mapping):
        scrubbed = {}
        for k, v in data.items():
            if str(k).lower() in sensitive_keys:
                scrubbed[k] = "[REDACTED]"
            else:
                scrubbed[k] = redact_sensitive_payload(v, sensitive_keys)
        return scrubbed
    elif isinstance(data, (list, tuple, set)):
        return [redact_sensitive_payload(item, sensitive_keys) for item in data]
    return data
