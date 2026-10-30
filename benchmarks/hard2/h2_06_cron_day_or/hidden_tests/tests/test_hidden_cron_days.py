from datetime import datetime

from flowkit.cron import CronSpec


def test_both_restricted_is_or():
    spec = CronSpec("0 9 1 * 1")
    assert spec.matches(datetime(2024, 6, 1, 9, 0))  # Saturday the 1st
    assert spec.matches(datetime(2024, 6, 3, 9, 0))  # Monday the 3rd
    assert not spec.matches(datetime(2024, 6, 4, 9, 0))


def test_next_after_or():
    spec = CronSpec("0 9 1 * 1")
    assert spec.next_after(datetime(2024, 5, 28, 10, 0)) == datetime(2024, 6, 1, 9, 0)
    assert spec.next_after(datetime(2024, 6, 1, 9, 0)) == datetime(2024, 6, 3, 9, 0)


def test_lists_ranges_or():
    spec = CronSpec("0 0 1,15 * 5")
    assert spec.matches(datetime(2024, 6, 15, 0, 0))  # Saturday the 15th
    assert spec.matches(datetime(2024, 6, 7, 0, 0))  # Friday
    assert not spec.matches(datetime(2024, 6, 8, 0, 0))


def test_star_step_day_is_unrestricted():
    spec = CronSpec("0 0 */2 * 1")
    assert spec.matches(datetime(2024, 6, 3, 0, 0))  # Monday, odd day
    assert not spec.matches(datetime(2024, 6, 10, 0, 0))  # Monday, even day
    assert not spec.matches(datetime(2024, 6, 5, 0, 0))  # odd day, Wednesday


def test_only_weekday_restricted():
    spec = CronSpec("0 0 * * 1")
    assert spec.matches(datetime(2024, 6, 3, 0, 0))
    assert not spec.matches(datetime(2024, 6, 1, 0, 0))


def test_only_day_restricted():
    spec = CronSpec("0 0 13 * *")
    assert spec.matches(datetime(2024, 6, 13, 0, 0))
    assert not spec.matches(datetime(2024, 6, 14, 0, 0))


def test_month_and_time_always_required():
    spec = CronSpec("30 9 1 6 1")
    assert not spec.matches(datetime(2024, 7, 1, 9, 30))
    assert not spec.matches(datetime(2024, 6, 3, 9, 31))
