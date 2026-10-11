"""Mathematical validation utilities for the Iranian National ID.

Implements the Modulo 11 checksum algorithm for the Iranian National Code
(کد ملی).
"""

from __future__ import annotations

import re


PERSIAN_ARABIC_DIGITS_TABLE = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalise_digits(text: str | None) -> str:
    """Convert Persian and Arabic numerals to standard ASCII digits."""
    if not text:
        return ""
    return str(text).translate(PERSIAN_ARABIC_DIGITS_TABLE)


def validate_national_code(code: str | None) -> bool:
    """Validate Iranian 10-digit National Code using official Modulo 11 checksum.

    Formula:
      Sum = sum(digit[i] * (10 - i)) for i in 0..8
      Remainder = Sum % 11
      If Remainder < 2: check_digit == Remainder
      If Remainder >= 2: check_digit == 11 - Remainder
    """
    clean = re.sub(r"\D", "", normalise_digits(code)).strip()
    if len(clean) != 10:
        return False

    # Disallow all repeated single-digit sequences (e.g. 0000000000, 1111111111)
    if clean in {str(i) * 10 for i in range(10)}:
        return False

    check_digit = int(clean[9])
    weighted_sum = sum(int(clean[i]) * (10 - i) for i in range(9))
    remainder = weighted_sum % 11

    if remainder < 2:
        return check_digit == remainder
    return check_digit == (11 - remainder)
