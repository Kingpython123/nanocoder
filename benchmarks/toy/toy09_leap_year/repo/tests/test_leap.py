from calendarx import days_in_month, is_leap


def test_common_leap():
    assert is_leap(2024)
    assert days_in_month(2024, 2) == 29


def test_century_not_leap():
    assert not is_leap(1900)


def test_400_is_leap():
    assert is_leap(2000)


def test_regular_month():
    assert days_in_month(2023, 4) == 30
