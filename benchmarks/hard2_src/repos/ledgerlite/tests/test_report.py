from decimal import Decimal

from ledgerlite import Converter, Invoice, StaticRates
from ledgerlite.report import render_report, report_rows


def make(number, amount, currency="EUR"):
    inv = Invoice(number, region="DE", currency=currency)
    inv.add_line("X", 1, amount, "books")
    return inv


def test_rows_sorted_single_currency():
    conv = Converter(StaticRates({("EUR", "USD"): "1.10"}))
    rows = report_rows([make("B", "20.00"), make("A", "10.00")], conv)
    assert rows == [("A", Decimal("10.00"), Decimal("10.00")), ("B", Decimal("20.00"), Decimal("20.00"))]


def test_render_total_line():
    conv = Converter(StaticRates({("EUR", "USD"): "1.10"}))
    text = render_report([make("A", "10.00"), make("B", "1234.50")], conv)
    assert text.splitlines()[-1].split() == ["TOTAL", "1,244.50", "EUR"]
