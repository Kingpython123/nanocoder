"""任务评测：在全新的仓库副本上打 patch，再跑 FAIL_TO_PASS / PASS_TO_PASS 测试。

评测和 agent 运行完全分开：agent 的沙箱里留下的任何东西（复现脚本、改过的测试）都不影响结果。
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from ..patch import get_patch
from ..sandbox import LocalSandbox
from .tasks import Task

PYTEST = "python -m pytest -q -p no:cacheprovider --no-header -rN"


@dataclass
class EvalResult:
    resolved: bool
    patch_applied: bool
    f2p_passed: bool
    p2p_passed: bool
    log: str = ""


def _pytest(sb: LocalSandbox, test_ids: list[str]) -> tuple[bool, str]:
    if not test_ids:
        return True, ""
    r = sb.run(f"{PYTEST} " + " ".join(shlex.quote(t) for t in test_ids), timeout=300)
    return r.exit_code == 0, r.output


def _overlay(sb: LocalSandbox, src: Path | None) -> None:
    """把 src 目录下的文件按相对路径写进沙箱（覆盖同名文件）。"""
    if src is None:
        return
    for f in Path(src).rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            sb.write_file(f.relative_to(src).as_posix(), f.read_text(encoding="utf-8"))


def evaluate_patch(task: Task, patch: str) -> EvalResult:
    if not patch.strip():
        return EvalResult(False, False, False, False, "empty patch")
    with LocalSandbox(task.repo_dir) as sb:
        sb.write_file(".nanocoder.patch", patch)
        r = sb.run("git apply --whitespace=nowarn .nanocoder.patch && rm .nanocoder.patch", timeout=60)
        if r.exit_code != 0:
            return EvalResult(False, False, False, False, "git apply failed:\n" + r.output)
        # 隐藏测试在打完 patch 之后才放进去，agent 对同名测试文件的改动也会被覆盖
        _overlay(sb, task.hidden_tests_dir)
        f2p_ok, f2p_log = _pytest(sb, task.fail_to_pass)
        p2p_ok, p2p_log = _pytest(sb, task.pass_to_pass)
    return EvalResult(f2p_ok and p2p_ok, True, f2p_ok, p2p_ok, f"[F2P]\n{f2p_log}\n[P2P]\n{p2p_log}")


def validate_task(task: Task) -> list[str]:
    """检查任务本身是否合格，返回问题列表（空 = 合格）。

    1. 原始代码上：每个 FAIL_TO_PASS 测试都必须失败，PASS_TO_PASS 必须全部通过
    2. 参考答案上：用和 agent 相同的流程生成 patch，评测必须 resolved
    """
    problems = []
    with LocalSandbox(task.repo_dir) as sb:
        _overlay(sb, task.hidden_tests_dir)
        for test_id in task.fail_to_pass:
            ok, _ = _pytest(sb, [test_id])
            if ok:
                problems.append(f"F2P 测试在原始代码上就通过了：{test_id}")
        ok, log = _pytest(sb, task.pass_to_pass)
        if not ok:
            problems.append(f"P2P 测试在原始代码上失败：\n{log[-800:]}")
        if task.solution_dir is None:
            problems.append("缺少 solution/ 参考答案")
            return problems
        _overlay(sb, task.solution_dir)
        patch = get_patch(sb)
    result = evaluate_patch(task, patch)
    if not result.resolved:
        problems.append(f"参考答案没有通过评测：\n{result.log[-800:]}")
    return problems
