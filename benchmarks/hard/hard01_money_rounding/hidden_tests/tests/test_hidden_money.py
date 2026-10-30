from decimal import Decimal

from ledgerlite import Invoice
from ledgerlite.money import format_money, round_money


def test_half_cent_rounds_up():
    assert round_money(Decimal("2.675")) == Decimal("2.68")
    assert round_money(Decimal("0.125")) == Decimal("0.13")
    assert round_money("1.005") == Decimal("1.01")


def test_negative_half_cent():
    assert round_money(Decimal("-2.675")) == Decimal("-2.68")
    assert round_money(Decimal("-0.125")) == Decimal("-0.13")


def test_invoice_line_total():
    inv = Invoice("R-1", region="DE")
    a = inv.add_line("A", 1, "2.675", "food")
    b = inv.add_line("B", 3, "0.335", "food")
    assert a.total == Decimal("2.68")
    assert b.total == Decimal("1.01")
    assert inv.total == Decimal("3.69")


def test_large_amount_precision():
    assert round_money(Decimal("12345678901234.565")) == Decimal("12345678901234.57")


def test_types_and_plain_values():
    assert isinstance(round_money(1), Decimal)
    assert round_money(1) == Decimal("1.00")
    assert round_money(0.1 + 0.2) == Decimal("0.30")
    assert round_money(Decimal("-1.234")) == Decimal("-1.23")


def test_format_small_negative():
    assert format_money(Decimal("-0.005")) == "-0.01 EUR"
