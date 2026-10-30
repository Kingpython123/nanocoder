"""Least-recently-used cache with optional TTL."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable, Hashable


class LRUCache:
    """When full, evicts the entry that was used least recently.

    get() and set() count as a use of the key; peek() and `in` do not.
    With `ttl` set, entries expire `ttl` seconds after they were last set.
    """

    def __init__(self, capacity: int, ttl: float | None = None, clock: Callable[[], float] = time.monotonic):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.ttl = ttl
        self._clock = clock
        self._data: OrderedDict[Hashable, tuple[Any, float | None]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _lookup(self, key: Hashable) -> tuple[Any, float | None] | None:
        """The live entry for `key`, or None. Expired entries are dropped."""
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry[1] is not None and self._clock() >= entry[1]:
            del self._data[key]
            return None
        return entry

    def get(self, key: Hashable, default: Any = None) -> Any:
        entry = self._lookup(key)
        if entry is None:
            self.misses += 1
            return default
        self._data.move_to_end(key)
        self.hits += 1
        return entry[0]

    def peek(self, key: Hashable, default: Any = None) -> Any:
        entry = self._lookup(key)
        return default if entry is None else entry[0]

    def set(self, key: Hashable, value: Any) -> None:
        expires = None if self.ttl is None else self._clock() + self.ttl
        self._data[key] = (value, expires)
        self._data.move_to_end(key)
        while len(self._data) > self.capacity:
            self._data.popitem(last=False)

    def delete(self, key: Hashable) -> bool:
        return self._data.pop(key, None) is not None

    def __contains__(self, key: Hashable) -> bool:
        return self._lookup(key) is not None

    def __len__(self) -> int:
        return len(self._data)

    def keys(self) -> list[Hashable]:
        """Keys from least to most recently used (expired entries included until touched)."""
        return list(self._data)
