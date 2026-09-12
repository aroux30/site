"""Mathematical validation utilities for Iranian National ID and Bank Cards (Karta Phase 1).

Implements:
- Modulo 11 checksum algorithm for Iranian National Code (کد ملی)
- Luhn algorithm for 16-digit bank card PANs
- 6-digit BIN prefix lookup for Iranian issuing banks
"""

from __future__ import annotations

import re

# Comprehensive mapping of Iranian Bank 6-digit BIN prefixes
IRANIAN_BANKS_BIN: dict[str, str] = {
    "603799": "بانک ملی ایران",
    "589210": "بانک سپه",
    "627648": "بانک توسعه صادرات",
    "627961": "بانک صنعت و معدن",
    "603770": "بانک کشاورزی",
    "628023": "بانک مسکن",
    "627760": "پست بانک ایران",
    "502908": "بانک توسعه تعاون",
    "627412": "بانک اقتصاد نوین",
    "622106": "بانک پارسیان",
    "502229": "بانک پاسارگاد",
    "627488": "بانک کارآفرین",
    "621986": "بانک سامان",
    "639346": "بانک سینا",
    "639607": "بانک سرمایه",
    "636214": "بانک آینده",
    "502806": "بانک شهر",
    "502938": "بانک دی",
    "603769": "بانک صادرات ایران",
    "610433": "بانک ملت",
    "627353": "بانک تجارت",
    "589463": "بانک رفاه کارگران",
    "627381": "بانک انصار",
    "505785": "بانک ایران زمین",
    "636949": "بانک حکمت ایرانیان",
    "505416": "بانک گردشگری",
    "606373": "بانک قرض‌الحسنه مهر ایران",
    "505801": "بانک قرض‌الحسنه رسالت",
}


def validate_national_code(code: str | None) -> bool:
    """Validate Iranian 10-digit National Code using official Modulo 11 checksum.

    Formula:
      Sum = sum(digit[i] * (10 - i)) for i in 0..8
      Remainder = Sum % 11
      If Remainder < 2: check_digit == Remainder
      If Remainder >= 2: check_digit == 11 - Remainder
    """
    clean = re.sub(r"\D", "", code or "").strip()
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


def validate_bank_card_luhn(card_number: str | None) -> bool:
    """Validate a 16-digit debit/credit card number using the Luhn algorithm."""
    clean = re.sub(r"\D", "", card_number or "").strip()
    if len(clean) != 16:
        return False

    digits = [int(d) for d in clean]
    checksum = 0
    for idx, d in enumerate(reversed(digits)):
        if idx % 2 == 1:
            doubled = d * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


def get_bank_name_by_bin(card_number: str | None) -> str:
    """Identify the Iranian issuing bank name using the 6-digit BIN prefix."""
    clean = re.sub(r"\D", "", card_number or "").strip()
    if len(clean) >= 6:
        bin_prefix = clean[:6]
        return IRANIAN_BANKS_BIN.get(bin_prefix, "شبکه بانکی شتاب")
    return "شبکه بانکی شتاب"
