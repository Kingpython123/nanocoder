import pytest

from flowkit.events import EventBus


def test_remaining_handlers_run():
    bus, seen = EventBus(), []

    def bad(p):
        raise RuntimeError("bad plugin")

    bus.subscribe("x", bad)
    bus.subscribe("x", lambda p: seen.append(p))
    with pytest.raises(RuntimeError, match="bad plugin"):
        bus.emit("x", 1)
    assert seen == [1]


def test_first_error_reraised():
    bus = EventBus()
    first, second = ValueError("first"), KeyError("second")

    def h1(p):
        raise first

    def h2(p):
        raise second

    bus.subscribe("x", h1)
    bus.subscribe("x", h2)
    with pytest.raises(ValueError) as exc:
        bus.emit("x")
    assert exc.value is first


def test_all_handlers_run_with_several_errors():
    bus, seen = EventBus(), []

    def bad(p):
        seen.append("bad")
        raise RuntimeError(p)

    bus.subscribe("x", bad)
    bus.subscribe("x", bad)
    bus.subscribe("x", lambda p: seen.append("ok"))
    with pytest.raises(RuntimeError):
        bus.emit("x", 1)
    assert seen == ["bad", "bad", "ok"]


def test_keyboard_interrupt_propagates_immediately():
    bus, seen = EventBus(), []

    def stop(p):
        raise KeyboardInterrupt

    bus.subscribe("x", stop)
    bus.subscribe("x", seen.append)
    with pytest.raises(KeyboardInterrupt):
        bus.emit("x", 1)
    assert seen == []


def test_once_removed_even_if_raises():
    bus = EventBus()

    def boom(p):
        raise RuntimeError

    bus.subscribe("x", boom, once=True)
    with pytest.raises(RuntimeError):
        bus.emit("x")
    assert bus.emit("x") == 0


def test_no_errors_returns_count():
    bus = EventBus()
    bus.subscribe("x", lambda p: None)
    assert bus.emit("x") == 1
