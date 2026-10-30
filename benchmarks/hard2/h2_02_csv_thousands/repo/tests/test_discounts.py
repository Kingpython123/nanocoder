from decimal import Decimal

import pytest

from ledgerlite.discounts import Discount, apply_discounts


def test_no_discounts():
    assert apply_discounts(Decimal("100"), []) == Decimal("100.00")


def test_single_percent():
    assert apply_discounts(Decimal("100"), [Discount.percent(10)]) == Decimal("90.00")


def test_fixed_after_percent():
    discounts = [Discount.fixed(10), Discount.percent(10)]
    assert apply_discounts(Decimal("100"), discounts) == Decimal("80.00")


def test_never_negative():
    assert apply_discounts(Decimal("5"), [Discount.fixed(20)]) == Decimal("0.00")


def test_validation():
    with pytest.raises(ValueError):
        Discount.percent(120)
    with pytest.raises(ValueError):
        Discount.fixed(-1)
    with pytest.raises(ValueError):
        Discount("bogus", Decimal(1))
