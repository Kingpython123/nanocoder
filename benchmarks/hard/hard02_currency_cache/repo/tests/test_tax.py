from decimal import Decimal

import pytest

from ledgerlite.tax import is_exempt, line_tax, tax_rate


def test_exempt_categories():
    assert is_exempt("food")
    assert is_exempt("books")
    assert not is_exempt("electronics")
    assert not is_exempt(None)


def test_line_tax_regions():
    assert line_tax(Decimal("100.00"), "electronics", "DE") == Decimal("19.00")
    assert line_tax(Decimal("100.00"), "electronics", "fr") == Decimal("20.00")
    assert line_tax(Decimal("100.00"), "food", "NL") == Decimal("0.00")


def test_unknown_region():
    with pytest.raises(ValueError):
        tax_rate("XX")
