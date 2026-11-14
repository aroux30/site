"""Multi-Factor Authentication (MFA) and TOTP service.

Provides:
1. Time-based One-Time Password (TOTP) generation and verification via PyOTP.
2. Cryptographic recovery codes generation.
"""

from __future__ import annotations

import logging
import secrets
import string
from typing import Any

import pyotp

logger = logging.getLogger("security.mfa")


# ── TOTP Helpers ─────────────────────────────────────────────────────────────


def generate_totp_secret() -> str:
    """Generate a fresh base32-encoded random secret for TOTP."""
    return pyotp.random_base32()


def get_totp_uri(
    secret: str,
    account_name: str,
    issuer_name: str = "IranianStore",
) -> str:
    """Generate the standard otpauth:// URI for QR code generation in authenticator apps."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=account_name, issuer_name=issuer_name)


def verify_totp_code(secret: str, code: str, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code with a configurable clock-skew window (+/- 30s by default)."""
    if not secret or not code:
        return False
    clean_code = code.strip().replace(" ", "")
    totp = pyotp.TOTP(secret)
    return bool(totp.verify(clean_code, valid_window=valid_window))


def generate_backup_codes(count: int = 8, length: int = 10) -> list[str]:
    """Generate secure single-use recovery/backup codes formatted as XXXXX-XXXXX."""
    alphabet = string.ascii_uppercase + string.digits
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(alphabet) for _ in range(length))
        formatted = f"{raw[:5]}-{raw[5:]}"
        codes.append(formatted)
    return codes
