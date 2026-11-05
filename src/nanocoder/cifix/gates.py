"""三道判定闸门，全部是确定性代码，模型绕不过去。

SWE-bench 的失败归因里，agent 看到 5 个测试失败后用 -k 排除，通过后提交。提交守卫只看“跑过 python 或
pytest”，拦不住。所以这里不信 agent 跑过什么，由 runner 自己跑配置里的命令。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..sandbox import Sandbox
from .config import ALWAYS_PROTECTED, Check

# 这些写法能让检查通过，却没有修任何东西。只看新增行
_SUPPRESSIONS = re.compile(
    r"#\s*noqa\b|#\s*type:\s*ignore|#\s*pyright:\s*ignore|#\s*pylint:\s*disable|#\s*ruff:\s*noqa"
    r"|#\s*pragma:\s*no cover|pytest\.mark\.(skip|skipif|xfail)\b|pytest\.(skip|xfail)\(|unittest\.skip|@skip\b"
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    command: str
    exit_code: int
    output: str
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def run_checks(sandbox: Sandbox, checks: tuple[Check, ...], timeout: float) -> list[CheckResult]:
    results = []
    for check in checks:
        r = sandbox.run(check.command, timeout=timeout)
        results.append(CheckResult(check.name, check.command, r.exit_code, r.output, r.timed_out))
    return results


def failing(results: list[CheckResult]) -> list[CheckResult]:
    return [r for r in results if not r.passed]


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def protected_violations(changed_files: list[str], patterns: tuple[str, ...]) -> list[str]:
    """路径闸门：返回碰了受保护路径的文件。"""
    regexes = [_glob_to_regex(p) for p in (*ALWAYS_PROTECTED, *patterns)]
    return [f for f in changed_files if any(r.match(f) for r in regexes)]


def suppressions_added(patch: str) -> list[str]:
    """返回 patch 新增的、用来屏蔽检查的行。"""
    found = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++") and _SUPPRESSIONS.search(line):
            found.append(line[1:].strip())
    return found
