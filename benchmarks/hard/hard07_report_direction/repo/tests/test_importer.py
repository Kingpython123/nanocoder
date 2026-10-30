from decimal import Decimal

import pytest

from ledgerlite.importer import parse_csv


def test_basic():
    items = parse_csv("sku,quantity,unit_price,category\nA1,2,3.50,food\nB2,1,10,electronics\n")
    assert [(i.sku, i.quantity, i.unit_price, i.category) for i in items] == [
        ("A1", 2, Decimal("3.50"), "food"),
        ("B2", 1, Decimal("10"), "electronics"),
    ]


def test_header_normalization_and_unknown_columns():
    items = parse_csv(" SKU , Quantity ,Unit Price,Warehouse\nA1, 3 , 1.25 ,north\n")
    assert items[0].sku == "A1"
    assert items[0].quantity == 3
    assert items[0].unit_price == Decimal("1.25")
    assert items[0].category == "general"


def test_blank_lines_skipped():
    text = "sku,quantity,unit_price\n\nA1,1,1.00\n   \nB2,2,2.00\n\n"
    assert [i.sku for i in parse_csv(text)] == ["A1", "B2"]


def test_empty_input():
    assert parse_csv("") == []


def test_missing_column():
    with pytest.raises(ValueError, match="unit_price"):
        parse_csv("sku,quantity\nA1,1\n")


def test_bad_quantity_mentions_row():
    with pytest.raises(ValueError, match="row 3"):
        parse_csv("sku,quantity,unit_price\nA1,1,1.00\nB2,two,1.00\n")
