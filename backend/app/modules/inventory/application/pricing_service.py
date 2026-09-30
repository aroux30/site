"""Tiered volume pricing engine adapter.

The canonical engine now lives under ``app.modules.pricing.application.pricing_service``.
This module re-exports the interface for full backward compatibility across all call sites.
"""

from __future__ import annotations

from app.modules.pricing.application.pricing_service import (
    calculate_dynamic_price,
    list_price_tiers,
    resolve_unit_price,
    set_price_tier,
)

__all__ = [
    "calculate_dynamic_price",
    "list_price_tiers",
    "resolve_unit_price",
    "set_price_tier",
]
