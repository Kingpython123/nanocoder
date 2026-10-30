"""Date helpers for schedules."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Iterable, TypeVar

D = TypeVar("D", bound=date)  # works for date and datetime


def month_end(d: D) -> D:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def add_months(d: D, months: int) -> D:
    """The same day `months` months later (negative = earlier).

    If that month is shorter, the result is its last day (Jan 31 + 1 month = Feb 28/29).
    Time of day and tzinfo of datetimes are kept.
    """
    total = d.year * 12 + (d.month - 1) + months
    year, month0 = divmod(total, 12)
    day = min(d.day, calendar.monthrange(year, month0 + 1)[1])
    return d.replace(year=year, month=month0 + 1, day=day)


def next_weekday(d: D, weekday: int) -> D:
    """Next date strictly after `d` that falls on `weekday` (Monday=0)."""
    days = (weekday - d.weekday() - 1) % 7 + 1
    return d + timedelta(days=days)


def add_business_days(d: D, n: int, holidays: Iterable[date] = ()) -> D:
    """Move `n` business days forward (or backward when n < 0).

    Business days are Monday-Friday that are not in `holidays` (dates). n=0 returns `d`
    if it is a business day, otherwise the next business day. Works for datetimes too:
    the time of day is kept and holidays still apply.
    """
    hols = set(holidays)

    def is_business_day(x: date) -> bool:
        return x.weekday() < 5 and x not in hols

    if n == 0:
        while not is_business_day(d):
            d += timedelta(days=1)
        return d
    for _ in range(n):
        d += timedelta(days=1)
        while not is_business_day(d):
            d += timedelta(days=1)
    return d
