from datetime import date, timedelta
from decimal import Decimal

from ledgerlite import Invoice
from ledgerlite.aging import aging_summary, bucket_for, overdue_list

TODAY = date(2024, 6, 30)


def inv(number, days_overdue, amount="100.00", paid=False):
    i = Invoice(number, region="DE", due=TODAY - timedelta(days=days_overdue), paid=paid)
    i.add_line("X", 1, amount, "food")
    return i


def test_bucket_for_inner_values():
    assert bucket_for(0) == "current"
    assert bucket_for(1) == "1-30"
    assert bucket_for(15) == "1-30"
    assert bucket_for(45) == "31-60"
    assert bucket_for(75) == "61-90"
    assert bucket_for(200) == "90+"


def test_summary():
    invoices = [inv("A", 10), inv("B", 45, "50.00"), inv("C", 120), inv("D", -5), inv("E", 10, paid=True)]
    totals = aging_summary(invoices, TODAY)
    assert totals == {
        "current": Decimal("100.00"),
        "1-30": Decimal("100.00"),
        "31-60": Decimal("50.00"),
        "61-90": Decimal("0.00"),
        "90+": Decimal("100.00"),
    }


def test_overdue_list_order():
    rows = overdue_list([inv("A", 10), inv("B", 45), inv("C", 120), inv("D", -5)], TODAY)
    assert rows == [("C", 120, "90+"), ("B", 45, "31-60"), ("A", 10, "1-30")]
