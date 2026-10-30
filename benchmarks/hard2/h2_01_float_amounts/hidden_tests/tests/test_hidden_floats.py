from decimal import Decimal

from ledgerlite import Converter, Discount, Invoice, LineItem, StaticRates
from ledgerlite.money import round_money, to_decimal


def test_to_decimal_float():
    assert to_decimal(0.1) == Decimal("0.1")
    assert to_decimal(1.005) == Decimal("1.005")


def test_add_line_float():
    inv = Invoice("F-1")
    line = inv.add_line("A", 1, 1.005, "food")
    assert line.total == Decimal("1.01")


def test_line_item_float():
    assert LineItem("A", 1, 2.675).total == Decimal("2.68")


def test_discount_float():
    assert Discount.fixed(0.1).value == Decimal("0.1")
    assert Discount.percent(12.5).value == Decimal("12.5")


def test_rates_float():
    conv = Converter(StaticRates({("EUR", "USD"): 1.1}))
    assert conv.rate("EUR", "USD") == Decimal("1.1")


def test_non_float_inputs_unchanged():
    assert to_decimal(3) == Decimal(3)
    assert to_decimal("2.50") == Decimal("2.50")
    assert to_decimal(1.5) == Decimal("1.5")
    assert round_money(Decimal("2.675")) == Decimal("2.68")
