"""Run steps in dependency order, retrying failures."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from .config import load_config
from .events import EventBus
from .graph import topo_order
from .retry import retry


@dataclass(frozen=True)
class Step:
    name: str
    func: Callable[[dict[str, Any]], Any]  # receives results of the steps run so far
    depends_on: tuple[str, ...] = ()


class Pipeline:
    def __init__(
        self,
        steps: Iterable[Step],
        config: Mapping[str, Any] | None = None,
        bus: EventBus | None = None,
        sleep: Callable[[float], None] = time.sleep,
        environ: Mapping[str, str] | None = None,
    ):
        self.steps = {s.name: s for s in steps}
        self.config = load_config(config, environ)
        self.bus = bus or EventBus()
        self._sleep = sleep

    def order(self) -> list[str]:
        return topo_order({name: s.depends_on for name, s in self.steps.items()})

    def _with_dependencies(self, names: Iterable[str]) -> set[str]:
        needed: set[str] = set()
        stack = list(names)
        while stack:
            name = stack.pop()
            if name not in self.steps:
                raise ValueError(f"unknown step {name!r}")
            if name in needed:
                continue
            needed.add(name)
            stack.extend(self.steps[name].depends_on)
        return needed

    def run(self, only: Iterable[str] | None = None) -> dict[str, Any]:
        """Run steps; returns {step name: return value}. Emits step.started / step.finished.

        With `only`, run just those steps plus everything they depend on, directly or
        indirectly; other steps are skipped. Unknown names raise ValueError.
        """
        order = self.order()
        if only is not None:
            needed = self._with_dependencies(only)
            order = [name for name in order if name in needed]
        retry_cfg = self.config["retry"]
        results: dict[str, Any] = {}
        for name in order:
            step = self.steps[name]
            self.bus.emit("step.started", name)
            results[name] = retry(
                lambda: step.func(results),
                max_retries=retry_cfg["max_retries"],
                base_delay=retry_cfg["base_delay"],
                max_delay=retry_cfg["max_delay"],
                sleep=self._sleep,
            )
            self.bus.emit("step.finished", name)
        return results
