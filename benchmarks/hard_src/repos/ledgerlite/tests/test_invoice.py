from decimal import Decimal

import pytest

from ledgerlite import Discount, Invoice, LineItem


def make_invoice():
    inv = Invoice("INV-1", region="DE")
    inv.add_line("CAB-1", 2, "10.00", "electronics")
    inv.add_line("APL-1", 1, "5.00", "food")
    return inv


def test_totals():
    inv = make_invoice()
    assert inv.subtotal == Decimal("25.00")
    assert inv.tax == Decimal("3.80")
    assert inv.gross == Decimal("28.80")
    assert inv.total == Decimal("28.80")


def test_total_with_discount():
    inv = make_invoice()
    inv.discounts.append(Discount.percent(10))
    assert inv.total == Decimal("25.92")


def test_negative_quantity_rejected():
    with pytest.raises(ValueError):
        LineItem("X", -1, Decimal("1"))
