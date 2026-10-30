from ledgerlite import Converter, Invoice, StaticRates
from ledgerlite.report import render_report, report_rows


def make(number):
    inv = Invoice(number)
    inv.add_line("X", 1, "1.00", "books")
    return inv


def numbers(names):
    conv = Converter(StaticRates({("EUR", "USD"): "1.10"}))
    return [r[0] for r in report_rows([make(n) for n in names], conv)]


def test_numbers_sort_naturally():
    assert numbers(["INV-10", "INV-9", "INV-11", "INV-1"]) == ["INV-1", "INV-9", "INV-10", "INV-11"]


def test_case_insensitive():
    assert numbers(["INV-4", "inv-3", "INV-2"]) == ["INV-2", "inv-3", "INV-4"]


def test_multiple_number_groups():
    assert numbers(["A10-1", "A2-10", "A2-9"]) == ["A2-9", "A2-10", "A10-1"]


def test_render_order():
    conv = Converter(StaticRates({("EUR", "USD"): "1.10"}))
    text = render_report([make("INV-10"), make("INV-9")], conv)
    assert [line.split()[0] for line in text.splitlines()[1:3]] == ["INV-9", "INV-10"]


def test_tie_is_deterministic():
    assert numbers(["INV-2", "INV-002"]) == ["INV-002", "INV-2"]
    assert numbers(["INV-002", "INV-2"]) == ["INV-002", "INV-2"]


def test_plain_alpha():
    assert numbers(["b", "a", "c"]) == ["a", "b", "c"]
