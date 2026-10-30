from decimal import Decimal

from ledgerlite.importer import parse_csv

HEADER = "sku,description,quantity,unit_price\n"


def test_quoted_comma():
    items = parse_csv(HEADER + 'C-7,"Cable, 2m",3,4.99\n')
    assert len(items) == 1
    assert items[0].description == "Cable, 2m"
    assert items[0].quantity == 3
    assert items[0].unit_price == Decimal("4.99")


def test_escaped_quotes():
    items = parse_csv(HEADER + 'M-1,"27"" monitor, matte",1,199.00\n')
    assert items[0].description == '27" monitor, matte'
    assert items[0].unit_price == Decimal("199.00")


def test_newline_inside_quotes():
    items = parse_csv(HEADER + 'N-1,"line one\nline two",2,1.50\nN-2,plain,1,2.00\n')
    assert [i.sku for i in items] == ["N-1", "N-2"]
    assert items[0].description == "line one\nline two"


def test_crlf_line_endings():
    items = parse_csv("sku,quantity,unit_price\r\nA1,1,1.00\r\n\r\nB2,2,2.00\r\n")
    assert [(i.sku, i.quantity) for i in items] == [("A1", 1), ("B2", 2)]


def test_trailing_empty_cell():
    items = parse_csv("sku,quantity,unit_price,category\nA1,1,1.00,\n")
    assert items[0].category == "general"


def test_blank_and_whitespace_lines():
    items = parse_csv("sku,quantity,unit_price\n\n  \nA1,1,1.00\n\n")
    assert [i.sku for i in items] == ["A1"]
