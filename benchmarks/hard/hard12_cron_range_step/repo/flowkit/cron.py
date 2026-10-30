"""5-field cron expressions (see README for the syntax)."""

from __future__ import annotations

from datetime import datetime, timedelta

FIELDS = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day", 1, 31),
    ("month", 1, 12),
    ("weekday", 0, 7),
)


class CronError(ValueError):
    pass


def parse_field(expr: str, lo: int, hi: int) -> frozenset[int]:
    """Expand one cron field into the set of matching values."""
    values: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        if not part:
            raise CronError(f"empty item in {expr!r}")
        rng, step_text = part, ""
        if part.startswith("*/"):
            rng, _, step_text = part.partition("/")
        try:
            step = int(step_text) if step_text else 1
            if rng == "*":
                start, end = lo, hi
            elif "-" in rng:
                a, b = rng.split("-", 1)
                start, end = int(a), int(b)
            elif step_text:
                raise CronError(f"a step needs '*' or a range: {part!r}")
            else:
                start = end = int(rng)
        except ValueError as e:
            if isinstance(e, CronError):
                raise
            raise CronError(f"bad cron item {part!r}") from None
        if step <= 0:
            raise CronError(f"step must be positive: {part!r}")
        if not lo <= start <= end <= hi:
            raise CronError(f"{part!r} is out of range {lo}-{hi}")
        values.update(range(start, end + 1, step))
    return frozenset(values)


class CronSpec:
    def __init__(self, expr: str):
        parts = expr.split()
        if len(parts) != 5:
            raise CronError(f"expected 5 fields, got {len(parts)}: {expr!r}")
        parsed = [parse_field(p, lo, hi) for p, (_, lo, hi) in zip(parts, FIELDS)]
        self.expr = expr
        self.minutes, self.hours, self.days, self.months, weekdays = parsed
        self.weekdays = frozenset(0 if d == 7 else d for d in weekdays)

    def matches(self, dt: datetime) -> bool:
        return (
            dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.day in self.days
            and dt.month in self.months
            and dt.isoweekday() % 7 in self.weekdays
        )

    def next_after(self, dt: datetime) -> datetime:
        """First matching minute strictly after `dt` (searches up to ~4 years)."""
        t = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(60 * 24 * 366 * 4):
            if self.matches(t):
                return t
            t += timedelta(minutes=1)
        raise CronError(f"{self.expr!r} never matches")

    def __repr__(self) -> str:
        return f"CronSpec({self.expr!r})"
