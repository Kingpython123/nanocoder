"""Coding Agent 的工具集：bash / view / search / edit / create / todo / submit。

每个任务新建一个 ToolRegistry，工具函数用闭包绑定当前任务的 sandbox 和 state，
agent loop 只管调用 registry.execute()，不需要知道沙箱的存在。

工具出错时返回以 "Error:" 开头的字符串，并且尽量告诉模型"下一步该怎么做"。
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from typing import Annotated

from pydantic import Field

from miniagent.tools import ToolRegistry, tool

from .sandbox import Sandbox, SandboxError

MAX_OUTPUT_CHARS = 10_000  # 单条工具输出上限
HEAD_CHARS = 4_000
TAIL_CHARS = 4_000
VIEW_MAX_LINES = 300
SEARCH_MAX_HITS = 50
EDIT_CONTEXT_LINES = 5

# 命令里出现这些词，就认为 agent "跑过验证"（提交守卫用）
_VERIFY_PATTERN = re.compile(r"\b(python3?|pytest)\b")


@dataclass
class AgentState:
    """一次任务运行中工具共享的状态。"""

    step: int = 0
    last_edit_step: int | None = None
    last_verify_step: int | None = None
    submitted: bool = False
    submit_blocked: bool = False  # 提交守卫只拦一次
    unverified_submit: bool = False
    todo: list[str] = field(default_factory=list)


def truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """超长输出保留头尾，中间写明省略了多少。"""
    if len(text) <= limit:
        return text
    head, tail = text[:HEAD_CHARS], text[-TAIL_CHARS:]
    omitted = text[HEAD_CHARS:-TAIL_CHARS]
    return (
        f"{head}\n\n... [output truncated: {omitted.count(chr(10))} lines / {len(omitted)} chars omitted. "
        f"Use head/tail/grep or a narrower command to see specific parts] ...\n\n{tail}"
    )


def _numbered(lines: list[str], start: int) -> str:
    width = len(str(start + len(lines)))
    return "\n".join(f"{i:>{width}} | {line}" for i, line in enumerate(lines, start))


def build_registry(sandbox: Sandbox, state: AgentState) -> ToolRegistry:
    registry = ToolRegistry()

    @tool
    def bash(
        command: Annotated[str, Field(description="Shell command to run (bash syntax).")],
        timeout: Annotated[int, Field(description="Timeout in seconds (max 600).")] = 120,
    ) -> str:
        """Run a shell command at the repository root and return its exit code and combined stdout/stderr.

        Use it to run tests (e.g. `python -m pytest tests/test_x.py -q`), run reproduction scripts, \
        or inspect the environment. Each call starts a fresh shell: `cd` and exported variables do not persist, \
        so chain commands with `&&` when needed. Long outputs are truncated; prefer targeted commands. \
        Do not use it to edit files (use `edit` / `create`), and do not start interactive programs or servers."""
        timeout = max(1, min(timeout, 600))
        if _VERIFY_PATTERN.search(command):
            state.last_verify_step = state.step
        result = sandbox.run(command, timeout=timeout)
        output = truncate(result.output) or "(no output)"
        if result.timed_out:
            return (
                f"Error: command timed out after {timeout}s and was killed. "
                "Run a narrower command (e.g. a single test file or `-x`), or raise `timeout`.\n"
                f"Partial output:\n{output}"
            )
        return f"exit code: {result.exit_code}\n{output}"

    @tool
    def view(
        path: Annotated[str, Field(description="File or directory path, relative to the repository root.")],
        start_line: Annotated[int | None, Field(description="First line to show (1-based).")] = None,
        end_line: Annotated[int | None, Field(description="Last line to show (inclusive).")] = None,
    ) -> str:
        """Show a file with line numbers, or list a directory (two levels deep).

        At most 300 lines are shown per call; use start_line / end_line to page through long files. \
        Line numbers are for reading only: do not include them in `edit`'s old_str."""
        if not sandbox.exists(path):
            return f"Error: {path!r} does not exist.{_similar_paths(sandbox, path)}"
        if sandbox.is_dir(path):
            r = sandbox.run(
                f"find {shlex.quote(path)} -maxdepth 2 -not -path '*/.git*' -not -name '__pycache__' | sort | head -200"
            )
            return r.output or "(empty directory)"
        lines = sandbox.read_file(path).splitlines()
        total = len(lines)
        if total == 0:
            return "(empty file)"
        start = max(1, start_line or 1)
        if start > total:
            return f"Error: start_line {start} is beyond the end of the file ({total} lines)."
        end = min(total, end_line or total, start + VIEW_MAX_LINES - 1)
        header = f"{path} ({total} lines total, showing {start}-{end})"
        if end < total:
            header += f"; use start_line={end + 1} to continue"
        return header + "\n" + _numbered(lines[start - 1 : end], start)

    @tool
    def search(
        pattern: Annotated[str, Field(description="Extended regular expression (grep -E syntax).")],
        path: Annotated[str, Field(description="Directory or file to search in.")] = ".",
        glob: Annotated[str | None, Field(description="Only search files matching this glob, e.g. '*.py'.")] = None,
    ) -> str:
        """Search file contents recursively and return matching lines as `path:line:text`.

        Returns at most 50 matches; narrow the pattern, path or glob if there are more."""
        include = f"--include={shlex.quote(glob)} " if glob else ""
        cmd = (
            f"grep -rnE --exclude-dir=.git --exclude-dir=__pycache__ {include}"
            f"-e {shlex.quote(pattern)} -- {shlex.quote(path)} | head -{SEARCH_MAX_HITS + 1}"
        )
        r = sandbox.run(cmd, timeout=60)
        hits = [line for line in r.output.splitlines() if line.strip()]
        if not hits:
            return f"No matches for {pattern!r} in {path!r}."
        if any(h.startswith("grep:") for h in hits) and len(hits) == 1:
            return f"Error: {hits[0]}"
        suffix = ""
        if len(hits) > SEARCH_MAX_HITS:
            hits = hits[:SEARCH_MAX_HITS]
            suffix = f"\n... more than {SEARCH_MAX_HITS} matches; narrow the pattern, path or glob."
        return truncate("\n".join(hits)) + suffix

    @tool
    def edit(
        path: Annotated[str, Field(description="File to edit, relative to the repository root.")],
        old_str: Annotated[str, Field(description="Exact text to replace. Must appear exactly once in the file, including indentation.")],
        new_str: Annotated[str, Field(description="Replacement text.")],
    ) -> str:
        """Replace one exact occurrence of old_str with new_str in a file.

        old_str must match the file exactly (whitespace and indentation included) and be unique; \
        include a few surrounding lines to make it unique. For Python files the result must still compile, \
        otherwise the edit is rejected and the file is left unchanged. Returns the edited region with line numbers."""
        if not sandbox.exists(path) or sandbox.is_dir(path):
            return f"Error: file {path!r} does not exist. Use `create` for new files.{_similar_paths(sandbox, path)}"
        if old_str == new_str:
            return "Error: old_str and new_str are identical; nothing to change."
        if not old_str:
            return "Error: old_str is empty. Provide the exact text to replace."
        content = sandbox.read_file(path)
        count = content.count(old_str)
        if count == 0:
            return "Error: old_str was not found in the file. " + _near_miss_hint(content, old_str, path)
        if count > 1:
            lines = _occurrence_lines(content, old_str)
            return (
                f"Error: old_str appears {count} times (starting at lines {', '.join(map(str, lines))}). "
                "Include more surrounding lines so that it matches exactly once."
            )
        new_content = content.replace(old_str, new_str, 1)
        if path.endswith(".py"):
            try:
                compile(new_content, path, "exec")
            except SyntaxError as e:
                return (
                    f"Error: the edit would make {path} invalid Python ({e.msg} at line {e.lineno}). "
                    "The file was NOT changed; fix the indentation or syntax of new_str and retry."
                )
        sandbox.write_file(path, new_content)
        state.last_edit_step = state.step
        start_line = content[: content.index(old_str)].count("\n") + 1
        new_lines = new_content.splitlines()
        lo = max(1, start_line - EDIT_CONTEXT_LINES)
        hi = min(len(new_lines), start_line + new_str.count("\n") + EDIT_CONTEXT_LINES)
        return f"Edited {path}. Lines {lo}-{hi} now read:\n" + _numbered(new_lines[lo - 1 : hi], lo)

    @tool
    def create(
        path: Annotated[str, Field(description="New file path, relative to the repository root.")],
        content: Annotated[str, Field(description="Full file content.")],
    ) -> str:
        """Create a new file, e.g. a reproduction script. Refuses to overwrite existing files (use `edit` for those)."""
        try:
            if sandbox.exists(path):
                return f"Error: {path!r} already exists. Use `edit` to modify it."
            sandbox.write_file(path, content)
        except SandboxError as e:
            return f"Error: {e}"
        state.last_edit_step = state.step
        return f"Created {path} ({content.count(chr(10)) + 1} lines)."

    @tool
    def todo(
        items: Annotated[list[str], Field(description="The full task list; each item like '[x] done thing' or '[ ] next thing'.")],
    ) -> str:
        """Replace your task list. Use it to plan multi-step work and track progress; the list survives context compression."""
        state.todo = list(items)
        return "Task list updated:\n" + "\n".join(state.todo)

    @tool
    def submit() -> str:
        """Finish the task and submit the current changes as the final patch. Only call this after verifying the fix."""
        if not state.submit_blocked:
            if state.last_edit_step is None:
                state.submit_blocked = True
                return (
                    "Error: you have not modified any file yet, so the patch would be empty. "
                    "Fix the issue first. (Call submit again only if you are certain no change is needed.)"
                )
            if state.last_verify_step is None or state.last_verify_step < state.last_edit_step:
                state.submit_blocked = True
                return (
                    "Error: you changed code but have not run any verification since your last edit. "
                    "Run your reproduction script or the relevant tests first, then submit again."
                )
        if state.last_edit_step is not None and (
            state.last_verify_step is None or state.last_verify_step < state.last_edit_step
        ):
            state.unverified_submit = True
        state.submitted = True
        return "Submitted."

    for t in (bash, view, search, edit, create, todo, submit):
        registry.register(t)
    return registry


def _similar_paths(sandbox: Sandbox, path: str) -> str:
    name = path.replace("\\", "/").rstrip("/").split("/")[-1]
    stem = name.split(".")[0][:4]  # 只取前几个字符，拼错的文件名也能匹配到
    if not stem:
        return ""
    r = sandbox.run(
        f"find . -iname {shlex.quote('*' + stem + '*')} -not -path '*/.git/*' | head -5", timeout=30
    )
    found = [line for line in r.output.splitlines() if line.strip()]
    return " Similar paths: " + ", ".join(found) if found else ""


def _occurrence_lines(content: str, needle: str) -> list[int]:
    lines, start = [], 0
    while (i := content.find(needle, start)) != -1:
        lines.append(content[:i].count("\n") + 1)
        start = i + 1
    return lines


def _near_miss_hint(content: str, old_str: str, path: str) -> str:
    """old_str 找不到时，用第一行非空内容做模糊定位，告诉模型去哪里看。"""
    first = next((line.strip() for line in old_str.splitlines() if line.strip()), "")
    if first:
        lines = [i for i, line in enumerate(content.splitlines(), 1) if first in line]
        if lines:
            return (
                f"Its first line appears at line(s) {', '.join(map(str, lines[:5]))}; "
                f"check indentation/whitespace there with `view {path}` and copy the text exactly."
            )
    return f"Use `view {path}` to copy the exact current text (do not include line numbers)."
