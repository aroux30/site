"""Unit tests for the Money value object."""

import pytest

from app.shared.money.money import Money


def test_money_creation():
    """Verify Rial and Toman constructors."""
    m_rial = Money.from_rials(100_000)
    assert m_rial.rials == 100_000
    assert m_rial.toman_value == 10_000

    m_toman = Money.toman(25_000)
    assert m_toman.rials == 250_000
    assert m_toman.toman_value == 25_000

    zero = Money.zero()
    assert zero.is_zero
    assert zero.rials == 0


def test_negative_money_rejected():
    """Verify negative money amounts raise ValueError."""
    with pytest.raises(ValueError):
        Money.from_rials(-100)

    with pytest.raises(ValueError):
        Money.toman(-50)


def test_money_arithmetic():
    """Verify addition, subtraction, and multiplication."""
    p1 = Money.toman(100_000)
    p2 = Money.toman(50_000)

    # Addition
    sum_m = p1 + p2
    assert sum_m.toman_value == 150_000
    assert sum_m.rials == 1_500_000

    # Subtraction
    diff_m = p1 - p2
    assert diff_m.toman_value == 50_000

    # Negative subtraction disallowed
    with pytest.raises(ValueError):
        _ = p2 - p1

    # Multiplication
    scaled = p2 * 3
    assert scaled.toman_value == 150_000
    assert 3 * p2 == scaled


def test_money_percentage_and_discount():
    """Verify percentage calculation and discount application."""
    total = Money.toman(1_000_000)  # 1,000,000 Toman

    # 10% discount
    discount_amount = total.percentage(10)
    assert discount_amount.toman_value == 100_000

    # Remaining after 10% discount
    after_discount = total.apply_discount(10)
    assert after_discount.toman_value == 900_000


def test_money_persian_formatting():
    """Verify Persian digit formatting."""
    m = Money.toman(250_000)
    fmt = m.format_toman()
    assert "تومان" in fmt
    # Persian digits for 250,000
    assert "۲۵۰,۰۰۰" in fmt
