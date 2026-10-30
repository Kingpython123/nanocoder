"""In-process publish / subscribe."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: defaultdict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler, *, once: bool = False) -> Callable[[], None]:
        """Register `handler`; returns a function that unsubscribes it.

        With once=True the handler is removed after its first call.
        """
        if once:

            def wrapper(payload: Any) -> None:
                self.unsubscribe(event, wrapper)
                handler(payload)

            target: Handler = wrapper
        else:
            target = handler
        self._handlers[event].append(target)
        return lambda: self.unsubscribe(event, target)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        try:
            self._handlers[event].remove(handler)
        except ValueError:
            pass

    def emit(self, event: str, payload: Any = None) -> int:
        """Call every handler subscribed to `event` at the time of the call; returns how many.

        A failing handler must not break the others: if a handler raises an Exception,
        the remaining handlers still run, and afterwards the first such exception is
        re-raised. BaseExceptions that are not Exceptions (KeyboardInterrupt, SystemExit)
        propagate immediately.
        """
        handlers = list(self._handlers.get(event, ()))
        first_error: Exception | None = None
        for h in handlers:
            try:
                h(payload)
            except Exception as e:
                if first_error is None:
                    first_error = e
        if first_error is not None:
            raise first_error
        return len(handlers)

    def handler_count(self, event: str) -> int:
        return len(self._handlers.get(event, ()))
