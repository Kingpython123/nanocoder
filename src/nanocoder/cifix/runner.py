"""CI 修复的主流程：复现闸门 → agent → 路径闸门 → 变绿闸门。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from ..agent import AgentResult
from ..patch import apply_patch, get_full_patch
from ..sandbox import Sandbox
from .config import CIConfig
from .env import EnvSetupError
from .gates import CheckResult, failing, protected_violations, run_checks, suppressions_added
from .logs import extract_failure

MAX_CHECK_OUTPUT = 6_000

FIXED = "fixed"
NOT_REPRODUCED = "not_reproduced"
SETUP_FAILED = "setup_failed"
AGENT_STOPPED = "agent_stopped"
NO_CHANGE = "no_change"
PROTECTED_PATH = "protected_path"
SUPPRESSION = "suppression"
NOT_GREEN = "not_green"


class Env(Protocol):
    def prepare(self) -> None: ...
    def open(self) -> Sandbox: ...
    def close(self) -> None: ...


AgentRunner = Callable[[str, Sandbox], AgentResult]


@dataclass
class Outcome:
    status: str
    detail: str = ""
    before: list[CheckResult] = field(default_factory=list)
    after: list[CheckResult] = field(default_factory=list)
    patch: str = ""  # 通过或被拒绝的 patch；status 不是 fixed 时不能交付
    changed_files: list[str] = field(default_factory=list)
    agent: AgentResult | None = None

    @property
    def fixed(self) -> bool:
        return self.status == FIXED


def build_task(config: CIConfig, before: list[CheckResult], ci_log: str | None) -> str:
    """失败输出是这次刚复现的，比 CI 日志可靠；CI 日志只作参考。这些内容都可能含不可信文本，放进标签里。"""
    parts = []
    for r in failing(before):
        state = "timed out" if r.timed_out else f"exit code {r.exit_code}"
        output = _untrusted(extract_failure(r.output, MAX_CHECK_OUTPUT))
        parts.append(f'<failing_check name="{r.name}" command="{r.command}" result="{state}">\n{output}\n</failing_check>')
    if ci_log:
        parts.append(f"<ci_log>\n{_untrusted(extract_failure(ci_log))}\n</ci_log>")
    commands = "\n".join(f"- {c.name}: `{c.command}`" for c in config.checks)
    parts.append(f"After your change, a clean environment will run ALL of these commands and every one must exit 0:\n{commands}")
    return "\n\n".join(parts)


def _untrusted(text: str) -> str:
    """防止日志内容提前闭合标签。"""
    return text.replace("</failing_check", "<\\/failing_check").replace("</ci_log", "<\\/ci_log")


def fix_ci(env: Env, config: CIConfig, run_agent: AgentRunner, ci_log: str | None = None) -> Outcome:
    timeout = config.limits.check_timeout
    try:
        env.prepare()
    except EnvSetupError as e:
        return Outcome(SETUP_FAILED, str(e))

    try:
        # 复现闸门：都通过就不调用模型
        with env.open() as sandbox:
            before = run_checks(sandbox, config.checks, timeout)
        if not failing(before):
            return Outcome(NOT_REPRODUCED, "All checks pass in a clean environment; the failure may be flaky or environment-specific.", before)

        with env.open() as sandbox:
            result = run_agent(build_task(config, before, ci_log), sandbox)
            patch, changed = get_full_patch(sandbox)
        outcome = Outcome(NOT_GREEN, before=before, patch=patch, changed_files=changed, agent=result)

        if result.exit_reason != "submitted":
            outcome.status, outcome.detail = AGENT_STOPPED, f"The agent stopped without submitting: {result.exit_reason} {result.error or ''}".strip()
            return outcome
        if not patch.strip():
            outcome.status, outcome.detail = NO_CHANGE, "The agent submitted no changes."
            return outcome

        # 路径闸门：拒绝，不静默剔除。修复可能正依赖被剔除的改动
        violations = protected_violations(changed, config.protected_paths)
        if violations:
            outcome.status, outcome.detail = PROTECTED_PATH, "Changed protected paths: " + ", ".join(violations)
            return outcome
        suppressions = suppressions_added(patch)
        if suppressions:
            outcome.status, outcome.detail = SUPPRESSION, "Added lines that silence checks: " + " | ".join(suppressions[:5])
            return outcome

        # 变绿闸门：新容器，打 patch，跑全部检查
        with env.open() as sandbox:
            applied = apply_patch(sandbox, patch)
            if applied:
                outcome.detail = f"The patch does not apply to a clean checkout: {applied}"
                return outcome
            outcome.after = run_checks(sandbox, config.checks, timeout)
        still_failing = failing(outcome.after)
        if still_failing:
            outcome.detail = "Still failing in a clean environment: " + ", ".join(r.name for r in still_failing)
            return outcome
        outcome.status = FIXED
        return outcome
    finally:
        env.close()


def fingerprint_payload(config: CIConfig, **extra: Any) -> dict[str, Any]:
    """运行配置指纹的内容：配置变了，结果就不能直接比较。"""
    return {
        "image": config.image,
        "setup": list(config.setup),
        "checks": [[c.name, c.command] for c in config.checks],
        "protected_paths": list(config.protected_paths),
        "limits": vars(config.limits),
        **extra,
    }
