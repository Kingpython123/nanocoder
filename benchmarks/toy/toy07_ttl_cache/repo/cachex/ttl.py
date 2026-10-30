import time


class TTLCache:
    """A tiny cache whose entries expire `ttl` seconds after being set."""

    def __init__(self, ttl: float, clock=time.monotonic):
        self.ttl = ttl
        self._clock = clock
        self._data = {}

    def set(self, key, value):
        self._data[key] = (value, self._clock())

    def get(self, key, default=None):
        if key not in self._data:
            return default
        value, stored_at = self._data[key]
        if self._clock() - stored_at > self.ttl:
            return value
        return default

    def __len__(self):
        return len(self._data)
