"""Tax calculation application service.

Computes taxes using configurable rules stored in the database, with support
for jurisdiction, product category, and effective date ranges.
Uses integer basis points (e.g. 1000 = 10.00%) to ensure zero floating-point drift.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.checkout.domain.models import TaxCategory, TaxRule

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Default standard VAT in Iran: 10% (1000 basis points)
DEFAULT_IRAN_VAT_BASIS_POINTS = 1000


class TaxService:
    """Provides tax calculation and tax rule querying."""

    @staticmethod
    async def get_effective_rule(
        db: AsyncSession,
        category: TaxCategory = TaxCategory.STANDARD,
        jurisdiction: str = "IR",
        effective_at: Optional[datetime] = None,
    ) -> Optional[TaxRule]:
        """Fetch the highest-priority active tax rule matching criteria."""
        now = effective_at or datetime.now(timezone.utc)

        stmt = (
            select(TaxRule)
            .where(
                TaxRule.is_active == True,  # noqa: E712
                TaxRule.category == category,
                TaxRule.jurisdiction == jurisdiction,
            )
            .order_by(TaxRule.priority.desc(), TaxRule.created_at.desc())
        )
        result = await db.execute(stmt)
        rules = list(result.scalars().all())

        for rule in rules:
            if rule.is_effective_at(now):
                return rule
        return None

    @staticmethod
    async def calculate_tax(
        db: AsyncSession,
        taxable_amount_rials: int,
        category: TaxCategory = TaxCategory.STANDARD,
        jurisdiction: str = "IR",
        effective_at: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Calculate tax on a given taxable amount in Rials.

        Returns:
            dict containing:
                - tax_amount_rials: int
                - rate_basis_points: int
                - rate_percent: float
                - category: str
                - rule_code: str
                - jurisdiction: str
        """
        if taxable_amount_rials <= 0:
            return {
                "tax_amount_rials": 0,
                "rate_basis_points": 0,
                "rate_percent": 0.0,
                "category": category.value,
                "rule_code": "ZERO_TAXABLE",
                "jurisdiction": jurisdiction,
            }

        if category == TaxCategory.EXEMPT or category == TaxCategory.ZERO:
            return {
                "tax_amount_rials": 0,
                "rate_basis_points": 0,
                "rate_percent": 0.0,
                "category": category.value,
                "rule_code": "EXEMPT",
                "jurisdiction": jurisdiction,
            }

        rule = await TaxService.get_effective_rule(
            db, category=category, jurisdiction=jurisdiction, effective_at=effective_at
        )

        if rule:
            rate_bp = rule.rate_basis_points
            rule_code = rule.code
        else:
            # Fallback to standard 10% Iranian VAT if database table not yet populated
            rate_bp = DEFAULT_IRAN_VAT_BASIS_POINTS
            rule_code = "IR_STANDARD_VAT_DEFAULT"

        # Deterministic integer tax calculation: (amount * basis_points) // 10000
        tax_amount = (taxable_amount_rials * rate_bp) // 10000

        await logger.adebug(
            "tax_calculated",
            amount=taxable_amount_rials,
            tax=tax_amount,
            basis_points=rate_bp,
            rule=rule_code,
        )

        return {
            "tax_amount_rials": tax_amount,
            "rate_basis_points": rate_bp,
            "rate_percent": rate_bp / 100.0,
            "category": category.value,
            "rule_code": rule_code,
            "jurisdiction": jurisdiction,
        }
