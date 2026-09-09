"""Integer-based Money value object for Iranian currency.

All monetary values are stored as **integers in Rials** to avoid floating-point
rounding errors.  Display helpers convert to/from Toman (1 Toman = 10 Rial).

Usage::

    price = Money.toman(150_000)          # 150,000 Toman
    assert price.rials == 1_500_000
    assert price.toman == 150_000

    total = price * 3                     # 450,000 Toman
    discounted = total - Money.toman(50_000)

Money objects are immutable, hashable, and comparable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

_RIAL_PER_TOMAN = 10


@dataclass(frozen=True, slots=True, order=True)
class Money:
    """Immutable value object representing Iranian currency.

    Internal representation is always **Rials** (the smallest unit).
    """

    rials: int

    # ── Constructors ──────────────────────────────────────────────────────

    @classmethod
    def zero(cls) -> Self:
        return cls(rials=0)

    @classmethod
    def from_rials(cls, amount: int) -> Self:
        if amount < 0:
            raise ValueError("Money amount cannot be negative")
        return cls(rials=amount)

    @classmethod
    def toman(cls, amount: int) -> Self:
        """Create a Money from a Toman value."""
        if amount < 0:
            raise ValueError("Money amount cannot be negative")
        return cls(rials=amount * _RIAL_PER_TOMAN)

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def toman_value(self) -> int:
        """Toman value (integer division, truncates sub-Toman rials)."""
        return self.rials // _RIAL_PER_TOMAN

    @property
    def is_zero(self) -> bool:
        return self.rials == 0

    # ── Arithmetic ────────────────────────────────────────────────────────

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(rials=self.rials + other.rials)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        result = self.rials - other.rials
        if result < 0:
            raise ValueError("Money subtraction would result in a negative amount")
        return Money(rials=result)

    def __mul__(self, factor: int) -> Money:
        if not isinstance(factor, int):
            return NotImplemented
        if factor < 0:
            raise ValueError("Cannot multiply Money by a negative factor")
        return Money(rials=self.rials * factor)

    def __rmul__(self, factor: int) -> Money:
        return self.__mul__(factor)

    # ── Display ───────────────────────────────────────────────────────────

    def format_toman(self) -> str:
        """Return a human-readable Persian-style formatted string, e.g. ``'۱۵۰,۰۰۰ تومان'``."""
        western = f"{self.toman_value:,}"
        # Convert to Persian digits
        table = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
        return f"{western.translate(table)} تومان"

    def format_rial(self) -> str:
        """Return a formatted Rial string."""
        western = f"{self.rials:,}"
        table = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
        return f"{western.translate(table)} ریال"

    def __str__(self) -> str:
        return self.format_toman()

    def __repr__(self) -> str:
        return f"Money(rials={self.rials})"

    # ── Percentage helpers ────────────────────────────────────────────────

    def percentage(self, pct: int) -> Money:
        """Return *pct* percent of this amount (integer arithmetic, truncated)."""
        return Money(rials=(self.rials * pct) // 100)

    def apply_discount(self, pct: int) -> Money:
        """Return the amount after subtracting *pct* percent."""
        if not 0 <= pct <= 100:
            raise ValueError("Discount percentage must be between 0 and 100")
        return Money(rials=self.rials - (self.rials * pct) // 100)
