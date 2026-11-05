"""从 CI 日志里截取关键部分。CI 日志动辄几万行，全给模型既贵又没用。"""

from __future__ import annotations

import re

MAX_LOG_CHARS = 8_000
CONTEXT_LINES = 3
TAIL_LINES = 30

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_GH_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z ")
_ERROR_LINE = re.compile(r"##\[error\]|\b(FAILED|FAIL|ERROR)\b|Traceback \(most recent|\w+Error\b|\berror:|\bfailed\b")


def clean_log(text: str) -> str:
    """去掉颜色控制符和 GitHub 加的时间戳。"""
    return "\n".join(_GH_TIMESTAMP.sub("", _ANSI.sub("", line)) for line in text.splitlines())


def extract_failure(text: str, limit: int = MAX_LOG_CHARS) -> str:
    """保留报错行及其上下文和日志结尾；放不下时优先保留结尾，那里通常有测试汇总。"""
    text = clean_log(text)
    if len(text) <= limit:
        return text
    lines = text.splitlines()
    keep = set(range(max(0, len(lines) - TAIL_LINES), len(lines)))
    tail_size = sum(len(lines[i]) + 1 for i in keep)
    size = tail_size
    for i, line in enumerate(lines):
        if not _ERROR_LINE.search(line):
            continue
        window = range(max(0, i - CONTEXT_LINES), min(len(lines), i + CONTEXT_LINES + 1))
        extra = sum(len(lines[j]) + 1 for j in window if j not in keep)
        if size + extra > limit:
            break
        keep.update(window)
        size += extra

    out: list[str] = []
    previous = -1
    for i in sorted(keep):
        if i != previous + 1:
            out.append(f"... [{i - previous - 1} lines omitted] ...")
        out.append(lines[i])
        previous = i
    return "\n".join(out)[-limit:]
