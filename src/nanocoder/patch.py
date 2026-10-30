"""从沙箱取出最终 patch。

只取已跟踪文件的改动（git diff）：agent 新建的复现脚本是未跟踪文件，自然不会进 patch。
测试文件的改动也剔除掉——评测时会用原始测试，改了测试文件只会造成冲突或作弊。
"""

from __future__ import annotations

from .sandbox import Sandbox

EXCLUDE_PATHSPECS = (
    "':(exclude,glob)**/tests/**'",
    "':(exclude,glob)**/test_*.py'",
    "':(exclude,glob)**/*_test.py'",
    "':(exclude,glob)**/conftest.py'",
)


def get_patch(sandbox: Sandbox) -> str:
    cmd = "git -c core.quotepath=off diff --no-color --no-ext-diff -- . " + " ".join(EXCLUDE_PATHSPECS)
    result = sandbox.run(cmd, timeout=60)
    if result.exit_code != 0:
        raise RuntimeError(f"git diff 失败：{result.output[:500]}")
    return result.output
