from flowkit.events import EventBus


def test_emit_calls_handlers_in_order():
    bus, seen = EventBus(), []
    bus.subscribe("x", lambda p: seen.append(("a", p)))
    bus.subscribe("x", lambda p: seen.append(("b", p)))
    assert bus.emit("x", 1) == 2
    assert seen == [("a", 1), ("b", 1)]


def test_unsubscribe_function():
    bus, seen = EventBus(), []
    off = bus.subscribe("x", seen.append)
    off()
    assert bus.emit("x", 1) == 0
    assert seen == []


def test_once_single_handler():
    bus, seen = EventBus(), []
    bus.subscribe("x", seen.append, once=True)
    bus.emit("x", 1)
    bus.emit("x", 2)
    assert seen == [1]
    assert bus.handler_count("x") == 0


def test_unknown_event():
    assert EventBus().emit("nothing") == 0
