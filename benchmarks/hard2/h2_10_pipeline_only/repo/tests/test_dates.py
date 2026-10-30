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


def test_add_business_days_forward():
    from flowkit.dates import add_business_days

    assert add_business_days(date(2024, 6, 7), 1) == date(2024, 6, 10)  # Fri -> Mon
    assert add_business_days(date(2024, 6, 3), 5) == date(2024, 6, 10)
    assert add_business_days(date(2024, 6, 3), 1, holidays=[date(2024, 6, 4)]) == date(2024, 6, 5)
    assert add_business_days(date(2024, 6, 8), 0) == date(2024, 6, 10)  # Sat -> Mon
