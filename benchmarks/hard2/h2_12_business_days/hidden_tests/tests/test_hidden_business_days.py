from datetime import date, datetime

from flowkit.dates import add_business_days


def test_backwards_simple():
    assert add_business_days(date(2024, 6, 3), -1) == date(2024, 5, 31)  # Mon -> Fri
    assert add_business_days(date(2024, 6, 5), -2) == date(2024, 6, 3)


def test_backwards_over_weekend_and_holiday():
    assert add_business_days(date(2024, 6, 4), -2, holidays=[date(2024, 6, 3)]) == date(2024, 5, 30)


def test_backwards_from_weekend():
    assert add_business_days(date(2024, 6, 9), -1) == date(2024, 6, 7)  # Sun -> Fri


def test_datetime_with_holidays():
    start = datetime(2024, 6, 3, 9, 30)
    assert add_business_days(start, 1, holidays=[date(2024, 6, 4)]) == datetime(2024, 6, 5, 9, 30)
    assert add_business_days(start, -1, holidays=[date(2024, 5, 31)]) == datetime(2024, 5, 30, 9, 30)


def test_forward_unchanged():
    assert add_business_days(date(2024, 6, 7), 1) == date(2024, 6, 10)
    assert add_business_days(date(2024, 6, 3), 10) == date(2024, 6, 17)


def test_zero_on_business_day():
    assert add_business_days(date(2024, 6, 5), 0) == date(2024, 6, 5)
