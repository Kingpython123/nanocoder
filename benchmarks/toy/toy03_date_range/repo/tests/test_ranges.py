from datetime import date
from calendarx import days_between


def test_inclusive():
    assert days_between(date(2024, 1, 1), date(2024, 1, 3)) == [
        date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)
    ]


def test_single_day():
    assert days_between(date(2024, 2, 29), date(2024, 2, 29)) == [date(2024, 2, 29)]


def test_reversed_is_empty():
    assert days_between(date(2024, 1, 5), date(2024, 1, 1)) == []
