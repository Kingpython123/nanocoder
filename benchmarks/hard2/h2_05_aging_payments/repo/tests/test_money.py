from decimal import Decimal

import pytest

from ledgerlite.money import format_money, round_money, to_decimal


def test_to_decimal_variants():
    assert to_decimal("12.50") == Decimal("12.50")
    assert to_decimal(3) == Decimal(3)
    assert to_decimal(" 7.25 ") == Decimal("7.25")


def test_to_decimal_rejects_garbage():
    with pytest.raises(ValueError):
        to_decimal("abc")
    with pytest.raises(ValueError):
        to_decimal(True)


def test_round_money_basic():
    assert round_money(Decimal("1.234")) == Decimal("1.23")
    assert round_money(Decimal("1.236")) == Decimal("1.24")
    assert round_money(10) == Decimal("10.00")
    assert isinstance(round_money("3.333"), Decimal)


def test_format_money():
    assert format_money(Decimal("1234.5")) == "1,234.50 EUR"
    assert format_money(-5, "USD") == "-5.00 USD"
    assert format_money(0) == "0.00 EUR"
