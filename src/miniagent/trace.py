"""追踪日志：把 agent 每一步做了什么记录下来，同时打印到终端和写入 JSONL 文件。

用法：

    tracer = Tracer()
    with timed() as t:
        message = llm.chat(messages, tools=...)
    tracer.log(step, "llm_call", message.content, duration=t.elapsed)

日志文件：logs/trace-<时间戳>.jsonl，每行一个 JSON 对象，例如
    {"time": "...", "step": 1, "type": "tool_call", "summary": "calculator(...)", "duration_ms": null}
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .config import PROJECT_ROOT

# 约定的步骤类型（也可以传别的字符串，比如 "error"）
STEP_TYPES = ("llm_call", "tool_call", "tool_result", "final")
_ICONS = {"llm_call": "🧠", "tool_call": "🔧", "tool_result": "📦", "final": "✅"}


class Timer:
    elapsed: float = 0.0


@contextmanager
def timed() -> Iterator[Timer]:
    """计时上下文管理器，退出后通过 t.elapsed 拿到耗时（秒）。"""
    t = Timer()
    start = time.perf_counter()
    try:
        yield t
    finally:
        t.elapsed = time.perf_counter() - start


class Tracer:
    def __init__(
        self,
        log_dir: str | Path | None = None,
        echo: bool = True,
        preview_chars: int = 160,
        max_summary_chars: int = 2000,
    ):
        now = datetime.now()
        stamp = f"{now:%Y%m%d-%H%M%S}-{now.microsecond // 1000:03d}"
        self.log_dir = Path(log_dir) if log_dir else PROJECT_ROOT / "logs"
        self.path = self.log_dir / f"trace-{stamp}.jsonl"  # 第一次 log 时才创建
        self.echo = echo
        self.preview_chars = preview_chars
        self.max_summary_chars = max_summary_chars

    def log(
        self,
        step: int,
        type: str,
        content: Any,
        *,
        duration: float | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """记录一条事件。

        step      第几轮循环（从 1 开始）
        type      llm_call / tool_call / tool_result / final
        content   任意内容，会被转成单行摘要
        duration  耗时（秒），可选
        extra     额外字段，例如 tool_call_id=...，会原样写入 JSONL
        """
        summary = _summarize(content)
        record: dict[str, Any] = {
            "time": datetime.now().isoformat(timespec="milliseconds"),
            "step": step,
            "type": type,
            "summary": _truncate(summary, self.max_summary_chars),
            "duration_ms": round(duration * 1000, 1) if duration is not None else None,
            **extra,
        }
        self._write(record)
        if self.echo:
            icon = _ICONS.get(type, "•")
            cost = f"  ({duration:.2f}s)" if duration is not None else ""
            print(f"  [step {step}] {icon} {type:<11} {_truncate(summary, self.preview_chars)}{cost}")
        return record

    def _write(self, record: dict[str, Any]) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _summarize(content: Any) -> str:
    """任意内容 -> 单行字符串。"""
    if content is None:
        return "（空）"
    if not isinstance(content, str):
        if hasattr(content, "model_dump"):  # pydantic / openai 对象
            content = content.model_dump(exclude_none=True)
        content = json.dumps(content, ensure_ascii=False, default=str)
    return " ".join(content.split())


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"
