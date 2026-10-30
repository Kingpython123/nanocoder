from flowkit.cache import LRUCache


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_set_get():
    c = LRUCache(2)
    c.set("a", 1)
    assert c.get("a") == 1
    assert c.get("missing", "dflt") == "dflt"
    assert (c.hits, c.misses) == (1, 1)


def test_capacity_evicts_oldest_set():
    c = LRUCache(2)
    c.set("a", 1)
    c.set("b", 2)
    c.set("a", 10)  # re-setting counts as a use
    c.set("c", 3)
    assert "b" not in c
    assert c.peek("a") == 10
    assert len(c) == 2


def test_ttl_expiry():
    clock = FakeClock()
    c = LRUCache(10, ttl=5, clock=clock)
    c.set("a", 1)
    clock.now = 4.9
    assert c.peek("a") == 1
    clock.now = 5.0
    assert c.get("a") is None
    assert len(c) == 0


def test_delete():
    c = LRUCache(2)
    c.set("a", 1)
    assert c.delete("a")
    assert not c.delete("a")
