"""Tax engine v1 — pure, I/O-free order tax calculation.

This module is deliberately free of database access: every input arrives as a
plain dataclass/dict and every output is a plain dataclass, so the whole
engine is unit-testable without a session. The async wrapper in
``tax_service_v2.py`` loads rules and resolves buyer context, then delegates
here.

Money rules (project-wide invariants):
    * amounts are integer Rials;
    * rates are integer basis points (900 = 9.00%);
    * all tax amounts use deterministic floor division ``(base * bp) // 10000``
      — no floats anywhere in the money path.

Rule semantics:
    * ``VAT``         — tax = base * bp / 10000, added to the customer total.
    * ``EXEMPT``      — no tax; the rule's ``exempt_reason`` is recorded.
    * ``COMPOUND``    — tax-on-tax: applied to (base + VAT of the same line).
    * ``WITHHOLDING`` — مالیات تکلیفی: withheld from the seller's proceeds, so
                        it is NOT added to the customer total. Applies only
                        when the buyer is B2B *and* holds a tax-exemption
                        certificate; a B2B buyer without a certificate is
                        taxed with VAT like any retail buyer.

Line resolution priority: product override > category override > default rule.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.modules.checkout.domain.tax_models import TaxRuleScope, TaxRuleType

BASIS_POINT_DENOMINATOR = 10_000

#: Rule code used when no active default rule exists (healthcheck warns too).
FALLBACK_RULE_CODE = "NO_ACTIVE_DEFAULT_RULE"


# ── Inputs ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TaxRuleData:
    """Plain-data view of a tax rule (decoupled from the ORM model)."""

    id: uuid.UUID | None
    code: str
    rule_type: str  # TaxRuleType value
    scope: str  # TaxRuleScope value
    rate_basis_points: int
    priority: int = 0
    category_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    is_active: bool = True
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    exempt_reason: str | None = None

    def is_effective_at(self, dt: datetime) -> bool:
        if not self.is_active:
            return False
        if self.effective_from and dt < self.effective_from:
            return False
        return not (self.effective_to and dt > self.effective_to)


@dataclass(frozen=True)
class OrderLineInput:
    """One order line as seen by the tax engine."""

    variant_id: uuid.UUID | None
    product_id: uuid.UUID | None
    category_id: uuid.UUID | None
    line_total_rial: int  # after proportional discount allocation


# ── Outputs ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LineTaxBreakdown:
    """Per-line tax result (all integer Rials)."""

    variant_id: uuid.UUID | None
    product_id: uuid.UUID | None
    category_id: uuid.UUID | None
    taxable_amount_rial: int
    rule_id: uuid.UUID | None
    rule_code: str
    rule_type: str
    rate_basis_points: int
    tax_amount_rial: int  # vat + compound (customer-facing tax for the line)
    vat_amount_rial: int
    compound_amount_rial: int
    withholding_amount_rial: int
    exempt_reason: str | None = None

    def to_snapshot_dict(self) -> dict[str, Any]:
        """JSON-serialisable shape persisted in OrderTaxObservation.lines."""
        return {
            "variant_id": str(self.variant_id) if self.variant_id else None,
            "product_id": str(self.product_id) if self.product_id else None,
            "category_id": str(self.category_id) if self.category_id else None,
            "taxable_amount_rial": self.taxable_amount_rial,
            "rule_id": str(self.rule_id) if self.rule_id else None,
            "rule_code": self.rule_code,
            "rule_type": self.rule_type,
            "rate_basis_points": self.rate_basis_points,
            "tax_amount_rial": self.tax_amount_rial,
            "vat_amount_rial": self.vat_amount_rial,
            "compound_amount_rial": self.compound_amount_rial,
            "withholding_amount_rial": self.withholding_amount_rial,
            "exempt_reason": self.exempt_reason,
        }


@dataclass(frozen=True)
class OrderTaxResult:
    """Full order tax result: per-line breakdown plus header totals."""

    lines: list[LineTaxBreakdown] = field(default_factory=list)
    vat_total_rial: int = 0
    withholding_total_rial: int = 0
    tax_total_rial: int = 0  # vat_total (incl. compound); customer-facing tax
    grand_total_rial: int = 0  # subtotal - discount + shipping + tax_total


# ── Engine ───────────────────────────────────────────────────────────────────


def _amount_with_bp(base: int, basis_points: int) -> int:
    """Deterministic integer tax: floor(base * bp / 10000)."""
    if base <= 0 or basis_points <= 0:
        return 0
    return (base * basis_points) // BASIS_POINT_DENOMINATOR


def _pick_rule(
    rules: list[TaxRuleData],
    *,
    product_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
) -> TaxRuleData | None:
    """Resolve the winning rule: product > category > default.

    Inside one scope bucket the highest ``priority`` wins; ties break on the
    later ``effective_from`` (newer version supersedes).
    """
    product_rules = [
        r
        for r in rules
        if r.scope == TaxRuleScope.PRODUCT.value
        and product_id is not None
        and r.product_id == product_id
    ]
    if product_rules:
        return max(
            product_rules,
            key=lambda r: (r.priority, r.effective_from or datetime.min.replace(tzinfo=UTC)),
        )

    category_rules = [
        r
        for r in rules
        if r.scope == TaxRuleScope.CATEGORY.value
        and category_id is not None
        and r.category_id == category_id
    ]
    if category_rules:
        return max(
            category_rules,
            key=lambda r: (r.priority, r.effective_from or datetime.min.replace(tzinfo=UTC)),
        )

    default_rules = [r for r in rules if r.scope == TaxRuleScope.DEFAULT.value]
    if default_rules:
        return max(
            default_rules,
            key=lambda r: (r.priority, r.effective_from or datetime.min.replace(tzinfo=UTC)),
        )
    return None


def _calculate_line(
    line: OrderLineInput,
    rule: TaxRuleData | None,
    *,
    withholding_applies: bool,
) -> LineTaxBreakdown:
    """Compute the tax breakdown for one line against its resolved rule."""
    base = max(int(line.line_total_rial), 0)

    if rule is None:
        # No rule at all: zero tax, loudly marked (the healthcheck surfaces
        # the missing default rule to admins).
        return LineTaxBreakdown(
            variant_id=line.variant_id,
            product_id=line.product_id,
            category_id=line.category_id,
            taxable_amount_rial=base,
            rule_id=None,
            rule_code=FALLBACK_RULE_CODE,
            rule_type=TaxRuleType.EXEMPT.value,
            rate_basis_points=0,
            tax_amount_rial=0,
            vat_amount_rial=0,
            compound_amount_rial=0,
            withholding_amount_rial=0,
            exempt_reason="no_active_default_rule",
        )

    rule_type = rule.rule_type
    rate = rule.rate_basis_points

    if rule_type == TaxRuleType.WITHHOLDING.value:
        if withholding_applies:
            withheld = _amount_with_bp(base, rate)
            return LineTaxBreakdown(
                variant_id=line.variant_id,
                product_id=line.product_id,
                category_id=line.category_id,
                taxable_amount_rial=base,
                rule_id=rule.id,
                rule_code=rule.code,
                rule_type=rule_type,
                rate_basis_points=rate,
                tax_amount_rial=0,
                vat_amount_rial=0,
                compound_amount_rial=0,
                withholding_amount_rial=withheld,
                exempt_reason=None,
            )
        # B2B buyer without a certificate (or retail buyer): the withholding
        # rule does not bind — the line falls back to zero VAT here unless a
        # VAT default picks it up. The caller resolves VAT separately; see
        # calculate_order_tax which re-resolves ignoring withholding rules.
        return LineTaxBreakdown(
            variant_id=line.variant_id,
            product_id=line.product_id,
            category_id=line.category_id,
            taxable_amount_rial=base,
            rule_id=rule.id,
            rule_code=rule.code,
            rule_type=rule_type,
            rate_basis_points=rate,
            tax_amount_rial=0,
            vat_amount_rial=0,
            compound_amount_rial=0,
            withholding_amount_rial=0,
            exempt_reason=None,
        )

    if rule_type == TaxRuleType.EXEMPT.value:
        return LineTaxBreakdown(
            variant_id=line.variant_id,
            product_id=line.product_id,
            category_id=line.category_id,
            taxable_amount_rial=base,
            rule_id=rule.id,
            rule_code=rule.code,
            rule_type=rule_type,
            rate_basis_points=0,
            tax_amount_rial=0,
            vat_amount_rial=0,
            compound_amount_rial=0,
            withholding_amount_rial=0,
            exempt_reason=rule.exempt_reason or rule.code,
        )

    if rule_type == TaxRuleType.COMPOUND.value:
        # Tax-on-tax: the compound rule's rate applies to the base alone here
        # (single-rule resolution); the caller composes it over the VAT line
        # when a VAT default also exists — see calculate_order_tax.
        compound = _amount_with_bp(base, rate)
        return LineTaxBreakdown(
            variant_id=line.variant_id,
            product_id=line.product_id,
            category_id=line.category_id,
            taxable_amount_rial=base,
            rule_id=rule.id,
            rule_code=rule.code,
            rule_type=rule_type,
            rate_basis_points=rate,
            tax_amount_rial=compound,
            vat_amount_rial=0,
            compound_amount_rial=compound,
            withholding_amount_rial=0,
            exempt_reason=None,
        )

    # Default: VAT
    vat = _amount_with_bp(base, rate)
    return LineTaxBreakdown(
        variant_id=line.variant_id,
        product_id=line.product_id,
        category_id=line.category_id,
        taxable_amount_rial=base,
        rule_id=rule.id,
        rule_code=rule.code,
        rule_type=TaxRuleType.VAT.value,
        rate_basis_points=rate,
        tax_amount_rial=vat,
        vat_amount_rial=vat,
        compound_amount_rial=0,
        withholding_amount_rial=0,
        exempt_reason=None,
    )


def calculate_order_tax(
    *,
    lines: list[OrderLineInput],
    rules: list[TaxRuleData],
    shipping_rial: int = 0,
    subtotal_rial: int = 0,
    discount_rial: int = 0,
    customer_is_b2b: bool = False,
    exemption_certificate: str | None = None,
    effective_at: datetime | None = None,
) -> OrderTaxResult:
    """Compute the full order tax breakdown. Pure function — zero I/O.

    Parameters
    ----------
    lines : per-line inputs with product/category identity and discounted
        line totals (integer Rials).
    rules : candidate rules (already loaded from the DB); the engine filters
        by effective window itself so callers can pass the whole active set.
    customer_is_b2b : buyer is a business customer (مالیات تکلیفی candidate).
    exemption_certificate : certificate reference; withholding applies only
        when the buyer is B2B *and* this is present.
    """
    now = effective_at or datetime.now(UTC)
    active_rules = [r for r in rules if r.is_effective_at(now)]
    withholding_applies = bool(customer_is_b2b and exemption_certificate)

    breakdowns: list[LineTaxBreakdown] = []
    for line in lines:
        rule = _pick_rule(
            active_rules, product_id=line.product_id, category_id=line.category_id
        )

        # Withholding rules bind only for certified B2B buyers. For everyone
        # else, re-resolve ignoring withholding rules so VAT still applies.
        if (
            rule is not None
            and rule.rule_type == TaxRuleType.WITHHOLDING.value
            and not withholding_applies
        ):
            non_withholding = [
                r for r in active_rules if r.rule_type != TaxRuleType.WITHHOLDING.value
            ]
            rule = _pick_rule(
                non_withholding,
                product_id=line.product_id,
                category_id=line.category_id,
            )

        breakdown = _calculate_line(
            line, rule, withholding_applies=withholding_applies
        )

        # Compose a compound default rule over the VAT line (tax-on-tax):
        # when the resolved rule is VAT and an active COMPOUND default exists,
        # the compound layer applies to (base + vat).
        if breakdown.rule_type == TaxRuleType.VAT.value and breakdown.vat_amount_rial > 0:
            compound_defaults = [
                r
                for r in active_rules
                if r.rule_type == TaxRuleType.COMPOUND.value
                and r.scope == TaxRuleScope.DEFAULT.value
            ]
            if compound_defaults:
                compound_rule = max(
                    compound_defaults,
                    key=lambda r: (
                        r.priority,
                        r.effective_from or datetime.min.replace(tzinfo=UTC),
                    ),
                )
                compound = _amount_with_bp(
                    breakdown.taxable_amount_rial + breakdown.vat_amount_rial,
                    compound_rule.rate_basis_points,
                )
                if compound > 0:
                    breakdown = LineTaxBreakdown(
                        variant_id=breakdown.variant_id,
                        product_id=breakdown.product_id,
                        category_id=breakdown.category_id,
                        taxable_amount_rial=breakdown.taxable_amount_rial,
                        rule_id=breakdown.rule_id,
                        rule_code=f"{breakdown.rule_code}+{compound_rule.code}",
                        rule_type=TaxRuleType.COMPOUND.value,
                        rate_basis_points=breakdown.rate_basis_points,
                        tax_amount_rial=breakdown.vat_amount_rial + compound,
                        vat_amount_rial=breakdown.vat_amount_rial,
                        compound_amount_rial=compound,
                        withholding_amount_rial=0,
                        exempt_reason=None,
                    )

        breakdowns.append(breakdown)

    vat_total = sum(b.tax_amount_rial for b in breakdowns)
    withholding_total = sum(b.withholding_amount_rial for b in breakdowns)
    grand_total = max(subtotal_rial, 0) - max(discount_rial, 0) + max(shipping_rial, 0) + vat_total
    grand_total = max(grand_total, 0)

    return OrderTaxResult(
        lines=breakdowns,
        vat_total_rial=vat_total,
        withholding_total_rial=withholding_total,
        tax_total_rial=vat_total,
        grand_total_rial=grand_total,
    )
