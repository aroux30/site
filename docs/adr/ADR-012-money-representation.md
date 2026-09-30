# ADR-012: Integer Storage for Money Representation

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform handles financial transactions in Iranian Rial (IRR) and displays prices in Toman (1 Toman = 10 Rial). Accurate monetary calculations are critical for pricing, discounts, tax computation, payment processing, and financial reporting.

Floating-point numbers (`float`, `double`) are fundamentally unsuitable for monetary values due to IEEE 754 representation errors. For example, `0.1 + 0.2 = 0.30000000000000004` in most programming languages. These rounding errors accumulate across calculations and can cause financial discrepancies.

Alternatives evaluated:

1. **Floating-point (float/double).** Fast but inherently imprecise for decimal arithmetic. Unacceptable for financial data.
2. **Decimal types (Python `Decimal`, PostgreSQL `NUMERIC`).** Precise decimal arithmetic but with higher computational overhead and more complex serialization in JSON APIs.
3. **Integer storage (smallest currency unit).** Store all monetary values as integers in the smallest meaningful unit (Rial). Simple, precise, and efficient.

## Decision

We will store all monetary values as **integers representing the smallest currency unit (Rial)** in the database and throughout the application. Conversion to Toman is performed exclusively at the presentation layer.

### Design Rules

1. **Database storage.** All money columns use `BIGINT` type, storing values in Rial.
2. **Application layer.** All monetary calculations use Python integers. No `float` is ever used for money.
3. **API layer.** API responses include both `price_rial` (integer) and `price_toman` (integer, computed as `price_rial // 10`) fields. API requests accept Rial values.
4. **Display layer.** The frontend formats Toman values with thousands separators for user display (e.g., `۱۲,۵۰۰ تومان`).
5. **Discount and tax calculations.** Percentage-based calculations use integer arithmetic with explicit rounding rules: `discount_rial = (price_rial * discount_percent) // 100`. Rounding always favors the customer (round down for discounts, round up for charges).
6. **Payment gateway integration.** All payment gateways in Iran expect amounts in Rial. Since internal storage is already in Rial, no conversion is needed at the payment boundary.

### Why Not Decimal?

While PostgreSQL `NUMERIC` and Python `Decimal` provide precise decimal arithmetic, integer storage is preferred because:

- Integers are simpler to reason about and cannot produce unexpected decimal places.
- Integer arithmetic is faster than decimal arithmetic.
- JSON serialization of integers is unambiguous; decimal serialization can produce strings or floating-point approximations depending on the serializer.
- The Iranian Rial has no subunit (no cents equivalent), so there is no need for fractional currency representation.

## Consequences

### Positive

- Zero risk of floating-point precision errors in any financial calculation.
- Simple and fast integer arithmetic throughout the entire stack.
- No conversion needed at the payment gateway boundary (gateways expect Rial).
- Unambiguous JSON serialization — integers are integers in every language and parser.
- `BIGINT` supports values up to 9.2 quintillion Rial, far exceeding any realistic transaction or aggregate amount.

### Negative

- Developers must consistently use Rial as the internal unit. Mixing Toman and Rial in calculations would produce 10x errors.
- Integer division for percentage calculations requires explicit rounding rules. Naive division can silently truncate.
- If the platform expands to currencies with subunits (e.g., USD with cents), the integer strategy still works but requires defining the base unit per currency.

### Mitigations

- We enforce a project-wide convention: all internal monetary values are in Rial. Variable names include the unit suffix (e.g., `price_rial`, `discount_rial`). Code review and linting rules flag money variables without the suffix.
- A `Money` value object class encapsulates monetary values, enforces Rial-based integer storage, and provides methods for safe arithmetic with explicit rounding.
- Conversion functions (`rial_to_toman`, `toman_to_rial`) are centralized in the `Money` class, preventing ad-hoc division/multiplication scattered across the codebase.
- Integration tests verify that payment amounts sent to gateways exactly match expected Rial values.
