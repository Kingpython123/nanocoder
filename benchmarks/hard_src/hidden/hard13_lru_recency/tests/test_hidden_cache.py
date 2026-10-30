from flowkit.cache import LRUCache


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_get_refreshes_recency():
    c = LRUCache(2)
    c.set("a", 1)
    c.set("b", 2)
    assert c.get("a") == 1
    c.set("c", 3)
    assert c.peek("a") == 1
    assert "b" not in c


def test_keys_order_after_get():
    c = LRUCache(3)
    for k in "abc":
        c.set(k, k)
    c.get("a")
    assert c.keys() == ["b", "c", "a"]


def test_peek_does_not_refresh():
    c = LRUCache(2)
    c.set("a", 1)
    c.set("b", 2)
    assert c.peek("a") == 1
    c.set("c", 3)
    assert "a" not in c
    assert c.keys() == ["b", "c"]


def test_contains_does_not_refresh():
    c = LRUCache(2)
    c.set("a", 1)
    c.set("b", 2)
    assert "a" in c
    c.set("c", 3)
    assert c.keys() == ["b", "c"]


def test_expired_get_counts_miss():
    clock = FakeClock()
    c = LRUCache(2, ttl=1, clock=clock)
    c.set("a", 1)
    clock.now = 2
    assert c.get("a", "gone") == "gone"
    assert (c.hits, c.misses) == (0, 1)
