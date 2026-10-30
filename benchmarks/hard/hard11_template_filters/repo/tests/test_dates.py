from datetime import date, datetime

from flowkit.dates import add_months, month_end, next_weekday


def test_add_months_simple():
    assert add_months(date(2024, 1, 15), 1) == date(2024, 2, 15)
    assert add_months(date(2024, 11, 15), 3) == date(2025, 2, 15)
    assert add_months(date(2024, 3, 10), -4) == date(2023, 11, 10)


def test_add_months_keeps_time():
    assert add_months(datetime(2024, 5, 20, 8, 30), 2) == datetime(2024, 7, 20, 8, 30)


def test_month_end():
    assert month_end(date(2024, 2, 10)) == date(2024, 2, 29)
    assert month_end(date(2023, 2, 10)) == date(2023, 2, 28)


def test_next_weekday():
    assert next_weekday(date(2024, 6, 3), 0) == date(2024, 6, 10)  # Monday -> next Monday
    assert next_weekday(date(2024, 6, 3), 4) == date(2024, 6, 7)
