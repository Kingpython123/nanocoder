from decimal import Decimal

import pytest

from ledgerlite.importer import parse_csv

DE_HEADER = "sku;quantity;unit_price\n"


def test_german_thousands():
    items = parse_csv(DE_HEADER + "A1;2;0,99\nB2;1.000;1.234,56\n", delimiter=";", decimal=",")
    assert [(i.quantity, i.unit_price) for i in items] == [(2, Decimal("0.99")), (1000, Decimal("1234.56"))]


def test_negative_german():
    items = parse_csv(DE_HEADER + "R1;1;-1.234,50\n", delimiter=";", decimal=",")
    assert items[0].unit_price == Decimal("-1234.50")


def test_space_grouping():
    text = DE_HEADER + "A1;1;1 234,56\nB2;1;12 345,00\n"
    items = parse_csv(text, delimiter=";", decimal=",")
    assert [i.unit_price for i in items] == [Decimal("1234.56"), Decimal("12345.00")]


def test_english_grouping():
    text = 'sku,quantity,unit_price\nA1,"2,000","1,234.50"\nB2,1,1 000.25\n'
    items = parse_csv(text)
    assert [(i.quantity, i.unit_price) for i in items] == [(2000, Decimal("1234.50")), (1, Decimal("1000.25"))]


def test_plain_numbers_both_modes():
    assert parse_csv("sku,quantity,unit_price\nA,3,4.25\n")[0].unit_price == Decimal("4.25")
    assert parse_csv(DE_HEADER + "A;3;4,25\n", delimiter=";", decimal=",")[0].unit_price == Decimal("4.25")


def test_bad_number_still_reports_row():
    with pytest.raises(ValueError, match="row 2"):
        parse_csv(DE_HEADER + "A;x;1,00\n", delimiter=";", decimal=",")
