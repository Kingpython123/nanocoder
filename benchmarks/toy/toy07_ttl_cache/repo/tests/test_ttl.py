from cachex import TTLCache


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_fresh_value_returned():
    clock = FakeClock()
    c = TTLCache(10, clock=clock)
    c.set("a", 1)
    clock.now = 5
    assert c.get("a") == 1


def test_expired_value_hidden():
    clock = FakeClock()
    c = TTLCache(10, clock=clock)
    c.set("a", 1)
    clock.now = 11
    assert c.get("a", "gone") == "gone"


def test_missing_key_default():
    assert TTLCache(10).get("nope", 42) == 42
