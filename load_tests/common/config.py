"""Configuration and constants for enterprise stress load testing."""

import os
from typing import Final

# Target host URL (can be overridden via TARGET_URL environment variable)
TARGET_HOST: Final[str] = os.environ.get("TARGET_HOST", "https://site.arouxpingg.com")

# Custom load testing bypass token for edge reverse-proxies
LOAD_TEST_SECRET_HEADER: Final[dict[str, str]] = {
    "X-Load-Test-Bypass": os.environ.get("LOAD_TEST_BYPASS_TOKEN", "stress-test-authorized-2026"),
    "X-Client-Platform": "web-stress-runner",
}

# SLA Target Thresholds for Performance Certification
SLA_MAX_FAIL_RATIO: Final[float] = 0.01  # Max 1.0% failures allowed
SLA_MAX_P95_MS: Final[float] = 600.0     # 95th percentile under 600ms
SLA_MAX_P99_MS: Final[float] = 1800.0    # 99th percentile under 1800ms
SLA_MIN_RPS: Final[float] = 1000.0       # Minimum sustained RPS target

# Persian search terms including Half-Space (ZWNJ: \u200c)
PERSIAN_SEARCH_QUERIES: Final[list[str]] = [
    "گوشی\u200cهای هوشمند",
    "لپ\u200cتاپ گیمینگ",
    "ساعت هوشمند",
    "هدفون بی\u200cسیم",
    "پاوربانک فست شارژ",
    "کفش ورزشی",
    "تبلت گرافیکی",
    "کیبورد مکانیکی",
    "مانیتور خمیده",
    "کارت گرافیک",
    "اسپیکر بلوتوثی",
    "فلش مموری",
]

# Common Iranian sample phones and cities for checkout simulation
SAMPLE_PROVINCES: Final[list[str]] = [
    "تهران",
    "اصفهان",
    "فارس",
    "خراسان رضوی",
    "آذربایجان شرقی",
    "مازندران",
    "خوزستان",
]
