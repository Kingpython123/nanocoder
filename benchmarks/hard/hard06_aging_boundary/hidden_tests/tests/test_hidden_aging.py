from datetime import date, timedelta
from decimal import Decimal

from ledgerlite import Invoice
from ledgerlite.aging import aging_summary, bucket_for, overdue_list

TODAY = date(2024, 6, 30)


def inv(number, days_overdue, amount="100.00"):
    i = Invoice(number, region="DE", due=TODAY - timedelta(days=days_overdue))
    i.add_line("X", 1, amount, "food")
    return i


def test_summary_boundaries():
    invoices = [inv("A", 30, "1.00"), inv("B", 31, "2.00"), inv("C", 60, "4.00"), inv("D", 90, "8.00"), inv("E", 91, "16.00")]
    totals = aging_summary(invoices, TODAY)
    assert totals["1-30"] == Decimal("1.00")
    assert totals["31-60"] == Decimal("6.00")
    assert totals["61-90"] == Decimal("8.00")
    assert totals["90+"] == Decimal("16.00")


def test_overdue_list_boundaries():
    rows = overdue_list([inv("A", 30), inv("B", 60), inv("C", 90), inv("D", 61)], TODAY)
    assert rows == [("C", 90, "61-90"), ("D", 61, "61-90"), ("B", 60, "31-60"), ("A", 30, "1-30")]


def test_one_day_and_current():
    assert bucket_for(1) == "1-30"
    assert bucket_for(0) == "current"
    rows = overdue_list([inv("A", 1), inv("B", 0)], TODAY)
    assert rows == [("A", 1, "1-30")]


def test_paid_excluded():
    paid = inv("P", 30)
    paid.paid = True
    assert overdue_list([paid], TODAY) == []
    assert sum(aging_summary([paid], TODAY).values()) == Decimal("0.00")
