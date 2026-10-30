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
    ):
        self.steps = {s.name: s for s in steps}
        self.config = load_config(config)
        self.bus = bus or EventBus()
        self._sleep = sleep

    def order(self) -> list[str]:
        return topo_order({name: s.depends_on for name, s in self.steps.items()})

    def run(self) -> dict[str, Any]:
        """Run all steps; returns {step name: return value}. Emits step.started / step.finished."""
        retry_cfg = self.config["retry"]
        results: dict[str, Any] = {}
        for name in self.order():
            step = self.steps[name]
            self.bus.emit("step.started", name)
            results[name] = retry(
                lambda: step.func(results),
                max_retries=retry_cfg.get("max_retries") or 3,
                base_delay=retry_cfg.get("base_delay") or 0.1,
                max_delay=retry_cfg["max_delay"],
                sleep=self._sleep,
            )
            self.bus.emit("step.finished", name)
        return results
