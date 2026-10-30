"""Retry with exponential backoff."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def backoff_delays(max_retries: int, base_delay: float = 0.1, max_delay: float = 2.0) -> list[float]:
    """Delay before retry 1..max_retries: base_delay * 2**i, capped at max_delay."""
    return [min(base_delay * 2**i, max_delay) for i in range(max_retries)]


def retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call fn(). If it raises one of `retry_on`, retry it up to `max_retries` more times.

    So fn is called at most max_retries + 1 times. Between attempts we sleep for the
    next value of backoff_delays(); there is no sleep after the final failure, whose
    exception is re-raised. Exceptions not in `retry_on` propagate immediately.
    """
    delays = backoff_delays(max_retries, base_delay, max_delay)
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except retry_on:
            if attempt == max_retries:
                raise
            sleep(delays[attempt])
    raise AssertionError("unreachable")
