"""Single-source VAT rate — the admin settings field is the only authority.

Before this module there were four different rates in play (owner screenshot
review, 2026-10-09):

- the ``store.shipping_tax.tax_rate_percent`` admin field — stored 12, read
  by nothing;
- the v2 tax engine's seeded ``IR-VAT-DEFAULT`` rule — 9%, what orders were
  actually charged;
- the legacy ``TaxService`` fallback — 10% (its ``tax_rules`` table is empty);
- hard-coded «۱۰٪» labels in the cart / drawer / checkout.

Owner decision: one field, one rate. The rule engine, its admin panel, the
VAT report and the withholding profile were removed
(``_archived/tax-engine-removal-2026-10-09/``); this service reads the
settings field and every surface — quote, order creation, per-line snapshots
and the storefront labels — derives from it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.modules.settings.domain.models import SiteSetting

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

#: site_settings row that carries the field (key kept for backward
#: compatibility with the admin form; only ``tax_rate_percent`` remains in it).
SETTING_KEY = "store.shipping_tax"
SETTING_FIELD = "tax_rate_percent"

#: Fallback when the row/key is missing or unparseable. Matches the value the
#: engine actually charged (9% Iranian VAT) — a missing setting must never
#: silently tax at zero.
DEFAULT_TAX_RATE_PERCENT = 9


async def get_tax_rate_percent(db: AsyncSession) -> int:
    """Read the configured VAT rate (whole percent) from site settings."""
    stmt = select(SiteSetting).where(SiteSetting.key == SETTING_KEY)
    row = (await db.execute(stmt)).scalar_one_or_none()
    raw: Any = None
    if row is not None and isinstance(row.value, dict):
        raw = row.value.get(SETTING_FIELD)
    try:
        rate = int(round(float(str(raw).strip())))
    except (TypeError, ValueError):
        return DEFAULT_TAX_RATE_PERCENT
    # A rate outside 0..100 is a typo, not a tax policy.
    return rate if 0 <= rate <= 100 else DEFAULT_TAX_RATE_PERCENT


async def calculate_tax_rials(
    db: AsyncSession, taxable_amount_rials: int
) -> dict[str, Any]:
    """Deterministic integer tax: ``(amount * basis_points) // 10000``.

    Returns the same dict shape the callers relied on before the engine was
    removed (``tax_amount_rials`` / ``rate_basis_points`` / ``rate_percent``
    / ``rule_code``).
    """
    rate_percent = await get_tax_rate_percent(db)
    basis_points = rate_percent * 100
    amount = max(int(taxable_amount_rials), 0)
    tax = (amount * basis_points) // 10000
    return {
        "tax_amount_rials": tax,
        "rate_basis_points": basis_points,
        "rate_percent": float(rate_percent),
        "rule_code": "SETTINGS_TAX_RATE",
    }
