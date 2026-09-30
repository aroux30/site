"""Customer order printable receipt HTML/PDF renderer.

DEPRECATION NOTICE: This module has been renamed to ``order_receipt_renderer.py``
to eliminate naming collision with the fiscal tax invoicing module (``app.modules.invoicing``).
This adapter provides 100% backward compatibility for existing call sites.
"""

from __future__ import annotations

from app.modules.orders.application.order_receipt_renderer import (
    generate_invoice_html_for_order,
    gregorian_to_jalali,
    number_to_persian_words,
)

__all__ = [
    "generate_invoice_html_for_order",
    "gregorian_to_jalali",
    "number_to_persian_words",
]
