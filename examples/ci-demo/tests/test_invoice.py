from decimal import Decimal

import pytest

from invoice import invoice_total, line_total


def test_plain_total():
    assert line_total("19.99", 2) == Decimal("39.98")


def test_discount():
    assert line_total("100.00", 1, 15) == Decimal("85.00")


def test_half_cent_rounds_up():
    # 0.125 元要进位成 0.13，docstring 写的是四舍五入
    assert line_total("0.125", 1) == Decimal("0.13")


def test_invoice_total():
    assert invoice_total([("10.00", 1, 0), ("0.125", 1, 0)]) == Decimal("10.13")


def test_rejects_bad_discount():
    with pytest.raises(ValueError):
        line_total("1.00", 1, 101)
