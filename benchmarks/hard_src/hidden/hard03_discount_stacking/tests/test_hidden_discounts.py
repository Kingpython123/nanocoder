from decimal import Decimal

from ledgerlite import Discount, Invoice
from ledgerlite.discounts import apply_discounts


def test_two_ten_percent():
    assert apply_discounts(Decimal("100"), [Discount.percent(10), Discount.percent(10)]) == Decimal("81.00")


def test_two_fifty_percent():
    assert apply_discounts(Decimal("100"), [Discount.percent(50), Discount.percent(50)]) == Decimal("25.00")


def test_invoice_with_stacked_coupons():
    inv = Invoice("S-1", region="DE")
    inv.add_line("BOOK", 1, "200.00", "books")
    inv.discounts += [Discount.fixed(20), Discount.percent(10), Discount.percent(5)]
    assert inv.total == Decimal("151.00")


def test_rounding_once_at_end():
    # 0.05 * 0.5 * 0.5 = 0.0125 -> 0.01 (rounding after each step would give 0.02)
    assert apply_discounts(Decimal("0.05"), [Discount.percent(50), Discount.percent(50)]) == Decimal("0.01")


def test_percent_order_irrelevant():
    a = apply_discounts(Decimal("80"), [Discount.percent(5), Discount.percent(10)])
    b = apply_discounts(Decimal("80"), [Discount.percent(10), Discount.percent(5)])
    assert a == b


def test_fixed_only_and_clamp():
    assert apply_discounts(Decimal("30"), [Discount.fixed(10), Discount.fixed(15)]) == Decimal("5.00")
    assert apply_discounts(Decimal("30"), [Discount.fixed(10), Discount.fixed(25)]) == Decimal("0.00")
