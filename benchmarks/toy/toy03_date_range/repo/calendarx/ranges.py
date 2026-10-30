from datetime import date, timedelta


def days_between(start: date, end: date) -> list[date]:
    """All dates from `start` to `end`, inclusive on both ends. Empty if end < start."""
    return [start + timedelta(days=i) for i in range((end - start).days)]
