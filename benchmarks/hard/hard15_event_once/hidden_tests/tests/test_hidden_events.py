from flowkit.events import EventBus


def test_once_does_not_skip_next():
    bus, seen = EventBus(), []
    bus.subscribe("x", lambda p: seen.append("once"), once=True)
    bus.subscribe("x", lambda p: seen.append("always"))
    bus.emit("x")
    bus.emit("x")
    assert seen == ["once", "always", "always"]


def test_self_unsubscribe_does_not_skip_next():
    bus, seen = EventBus(), []

    def first(p):
        seen.append("first")
        off()

    off = bus.subscribe("x", first)
    bus.subscribe("x", lambda p: seen.append("second"))
    bus.emit("x")
    assert seen == ["first", "second"]


def test_emit_count_with_once():
    bus = EventBus()
    bus.subscribe("x", lambda p: None, once=True)
    bus.subscribe("x", lambda p: None)
    assert bus.emit("x") == 2
    assert bus.emit("x") == 1


def test_subscribe_during_emit():
    bus, seen = EventBus(), []

    def adder(p):
        seen.append(("adder", p))
        if p == 1:
            bus.subscribe("x", lambda q: seen.append(("late", q)))

    bus.subscribe("x", adder)
    bus.emit("x", 1)
    assert seen == [("adder", 1)]
    bus.emit("x", 2)
    assert seen == [("adder", 1), ("adder", 2), ("late", 2)]


def test_unsubscribe_unknown_is_noop():
    bus = EventBus()
    bus.unsubscribe("x", print)
    assert bus.handler_count("x") == 0
