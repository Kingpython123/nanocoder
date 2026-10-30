from datetime import date, datetime

from flowkit.dates import add_months


def test_clamps_to_month_end():
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert add_months(date(2024, 8, 31), 1) == date(2024, 9, 30)
    assert add_months(date(2024, 3, 31), 1) == date(2024, 4, 30)


def test_leap_years():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)


def test_negative_months_clamp():
    assert add_months(date(2024, 3, 31), -1) == date(2024, 2, 29)
    assert add_months(date(2023, 5, 31), -3) == date(2023, 2, 28)


def test_datetime_clamp_keeps_time():
    assert add_months(datetime(2024, 1, 31, 23, 59), 1) == datetime(2024, 2, 29, 23, 59)


def test_year_wrap_negative():
    assert add_months(date(2024, 1, 15), -13) == date(2022, 12, 15)


def test_short_day_not_extended():
    assert add_months(date(2023, 2, 28), 1) == date(2023, 3, 28)
