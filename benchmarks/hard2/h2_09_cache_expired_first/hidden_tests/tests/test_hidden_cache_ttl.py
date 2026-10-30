from flowkit.cache import LRUCache


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_expired_dropped_before_live():
    clock = FakeClock()
    c = LRUCache(3, ttl=10, clock=clock)
    c.set("old1", 1)
    c.set("old2", 2)
    clock.now = 5
    c.set("fresh", 3)
    clock.now = 6
    c.get("old1")  # reading refreshes recency, not the TTL
    c.get("old2")
    clock.now = 12  # old1 / old2 expired, fresh (least recently used) still live
    c.set("new", 4)
    assert c.peek("fresh") == 3
    assert c.peek("new") == 4


def test_len_counts_live_only():
    clock = FakeClock()
    c = LRUCache(5, ttl=10, clock=clock)
    c.set("a", 1)
    clock.now = 5
    c.set("b", 2)
    clock.now = 11
    assert len(c) == 1


def test_keys_live_only():
    clock = FakeClock()
    c = LRUCache(5, ttl=10, clock=clock)
    c.set("a", 1)
    clock.now = 5
    c.set("b", 2)
    c.set("c", 3)
    clock.now = 11
    assert c.keys() == ["b", "c"]


def test_lru_eviction_without_ttl():
    c = LRUCache(2)
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")
    c.set("c", 3)
    assert c.keys() == ["a", "c"]


def test_live_entries_still_evicted_lru():
    clock = FakeClock()
    c = LRUCache(2, ttl=100, clock=clock)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)
    assert c.keys() == ["b", "c"]


def test_purge_does_not_touch_counters():
    clock = FakeClock()
    c = LRUCache(2, ttl=1, clock=clock)
    c.set("a", 1)
    clock.now = 2
    c.set("b", 2)
    c.set("c", 3)
    len(c)
    c.keys()
    assert (c.hits, c.misses) == (0, 0)


def test_peek_does_not_refresh():
    c = LRUCache(2)
    c.set("a", 1)
    c.set("b", 2)
    c.peek("a")
    c.set("c", 3)
    assert "a" not in c
