"""验证报告。结果都来自 runner 的执行记录，模型的说明单独标出来，不当作证据。

报告会贴到 PR 上，用英文。
"""

from __future__ import annotations

from .gates import CheckResult
from .runner import (
    AGENT_STOPPED, FIXED, NO_CHANGE, NOT_GREEN, NOT_REPRODUCED, PROTECTED_PATH, SETUP_FAILED, SUPPRESSION, Outcome,
)  # fmt: skip

OUTPUT_TAIL = 1_500
_HEADLINES = {
    FIXED: "✅ Fixed: all checks pass in a clean environment",
    NOT_REPRODUCED: "⚪ Not reproduced: no model was called",
    SETUP_FAILED: "⚠️ The environment could not be set up",
    AGENT_STOPPED: "❌ Not fixed: the agent stopped early",
    NO_CHANGE: "❌ Not fixed: the agent made no changes",
    PROTECTED_PATH: "🚫 Rejected: the change touches protected paths",
    SUPPRESSION: "🚫 Rejected: the change silences checks",
    NOT_GREEN: "❌ Not fixed: checks still fail in a clean environment",
}


def agent_note(outcome: Outcome) -> str:
    """模型最后说的话。"""
    if outcome.agent is None:
        return ""
    for message in reversed(outcome.agent.messages):
        if message.get("role") == "assistant" and message.get("content"):
            return str(message["content"]).strip()
    return ""


def _check_table(results: list[CheckResult]) -> str:
    rows = ["| Check | Command | Result |", "|---|---|---|"]
    for r in results:
        state = "pass" if r.passed else ("timed out" if r.timed_out else f"fail (exit {r.exit_code})")
        command = r.command.replace("|", "\\|")
        rows.append(f"| {r.name} | `{command}` | {state} |")
    return "\n".join(rows)


def _failure_output(results: list[CheckResult]) -> str:
    blocks = []
    for r in results:
        if not r.passed:
            tail = r.output[-OUTPUT_TAIL:].replace("```", "'''")
            blocks.append(f"<details><summary>{r.name} output (last {OUTPUT_TAIL} characters)</summary>\n\n```text\n{tail}\n```\n\n</details>")
    return "\n\n".join(blocks)


def render_report(outcome: Outcome, fingerprint: str = "", model: str = "") -> str:
    parts = [f"## {_HEADLINES[outcome.status]}"]
    if outcome.detail:
        parts.append(outcome.detail)
    if outcome.before:
        parts += ["### Before the change", _check_table(outcome.before)]
        if output := _failure_output(outcome.before):
            parts.append(output)
    if outcome.after:
        parts += ["### After the change (clean environment)", _check_table(outcome.after)]
        if output := _failure_output(outcome.after):
            parts.append(output)
    if outcome.changed_files:
        parts += ["### Changed files", "\n".join(f"- `{f}`" for f in outcome.changed_files)]
    if note := agent_note(outcome):
        quoted = "\n".join(f"> {line}" for line in note.splitlines())
        parts += ["### Model's explanation", "Written by the model and not verified.", quoted]
    if outcome.agent:
        a = outcome.agent
        usage = f"{a.steps} steps, {a.prompt_tokens:,} input tokens ({a.cached_tokens:,} cached), {a.completion_tokens:,} output tokens, {a.wall_time:.0f}s"
        parts += ["### Run", usage]
    footer = " · ".join(x for x in (f"model `{model}`" if model else "", f"config `{fingerprint}`" if fingerprint else "") if x)
    if footer:
        parts.append(f"<sub>{footer}</sub>")
    return "\n\n".join(parts) + "\n"
