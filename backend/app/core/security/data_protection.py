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
from collections.abc import Mapping
from typing import Any


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
        '1234567011' -> '***-****-011'
        '1234567890' -> '***-****-890'
    """
    if not code:
        return ""
    clean = re.sub(r"\D", "", code).strip()
    if len(clean) == 10:
        return f"***-****-{clean[-3:]}"
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


def mask_address(address: str | None) -> str:
    """Mask detailed street and house address for customer/non-admin DTOs.

    Preserves general city/district context while redacting alley, building, and unit details.
    Example:
        'تهران، سعادت‌آباد، خیابان سرو غربی، پلاک ۱۲، واحد ۴' -> 'تهران، سعادت‌آباد ***'
    """
    if not address:
        return ""
    clean = address.strip()
    # Split by comma or whitespace to preserve the first segment and mask the rest
    if "،" in clean:
        parts = [p.strip() for p in clean.split("،") if p.strip()]
        if len(parts) >= 2:
            return f"{parts[0]}، {parts[1]} ***"
        return f"{parts[0]} ***"
    words = clean.split()
    if len(words) > 2:
        return f"{' '.join(words[:2])} ***"
    return f"{clean[:4]}***" if len(clean) > 4 else "***"


# Default sensitive keys to scrub from logs or customer payloads
DEFAULT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "jwt_secret",
        "jwt_secret_key",
        # Auth headers: logging a request/response envelope must never leak
        # the bearer credential it carried (see the dashboard/audit paths).
        "authorization",
        "auth_header",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "session",
        "cvv",
        "cvv2",
        "security_code",
        "pin",
        "private_key",
        "api_key",
        "national_code",
        "national_id",
        "card_number",
        "card_pan",
        "card_no",
        "pan",
        "sheba",
        "iban",
        "digital_cards_encryption_key",
    }
)

_MASK = "[REDACTED]"
_JWT_PATTERN = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+")
_BEARER_PATTERN = re.compile(r"(Bearer\s+)[a-zA-Z0-9._~+/-]+", re.IGNORECASE)
_BASIC_AUTH_PATTERN = re.compile(r"(Basic\s+)[a-zA-Z0-9+/=]+", re.IGNORECASE)


def _scrub_string(value: str) -> str:
    """Mask inline credentials embedded in free-form strings.

    A sensitive *key* is redacted wholesale; this catches the mirror case
    where the secret travels inside an otherwise-safe value (a log message
    such as ``"Header sent: Bearer <token>"``).
    """
    scrubbed = _BEARER_PATTERN.sub(r"\g<1>[REDACTED]", value)
    scrubbed = _BASIC_AUTH_PATTERN.sub(r"\g<1>[REDACTED]", scrubbed)
    if "eyJ" in scrubbed:
        scrubbed = _JWT_PATTERN.sub("[REDACTED_JWT]", scrubbed)
    return scrubbed


def redact_sensitive_payload(
    data: Any,
    sensitive_keys: frozenset[str] = DEFAULT_SENSITIVE_KEYS,
) -> Any:
    """Recursively scrub sensitive keys from dictionaries or lists for safe logging."""
    if isinstance(data, Mapping):
        scrubbed = {}
        for k, v in data.items():
            if str(k).lower() in sensitive_keys:
                scrubbed[k] = _MASK
            else:
                scrubbed[k] = redact_sensitive_payload(v, sensitive_keys)
        return scrubbed
    elif isinstance(data, (list, tuple, set)):
        return [redact_sensitive_payload(item, sensitive_keys) for item in data]
    elif isinstance(data, str):
        return _scrub_string(data)
    return data
