"""从沙箱取出最终 patch。

- 已跟踪文件的改动：git diff。
- agent 新建的文件：子目录里的新文件算作修复的一部分（例如新增一个模块），用 `git add -N`
  让 git diff 带上它们；仓库根目录下的新文件（复现脚本 reproduce.py 之类）不算。
  最早的版本只取已跟踪文件，SWE-bench 冒烟测试里 agent 新建的模块因此丢失，patch 引用了不存在的文件。
- 测试文件的改动全部剔除——评测时会用原始 / 隐藏测试，改了测试文件只会造成冲突或作弊。
"""

from __future__ import annotations

from .sandbox import Sandbox

EXCLUDE_PATHSPECS = (
    "':(exclude,glob)**/tests/**'",
    "':(exclude,glob)**/test_*.py'",
    "':(exclude,glob)**/*_test.py'",
    "':(exclude,glob)**/conftest.py'",
)

# 子目录里、未被 .gitignore 忽略的新文件，标记为 intent-to-add（不改变内容，只让 diff 看得到）
_ADD_NEW_FILES = (
    "git ls-files --others --exclude-standard -z | "
    "grep -z / | grep -zv -E '__pycache__|\\.pyc$' | xargs -0 -r git add -N --"
)


def get_full_patch(sandbox: Sandbox) -> tuple[str, list[str]]:
    """CI 修复用：取全部改动，不剔除任何文件（碰了受保护路径由闸门拒绝）。返回 (patch, 改动的文件)。

    --no-renames：重命名显示成一删一增，路径闸门才看得到被移走的测试文件。
    """
    r = sandbox.run("git add -A 2>&1", timeout=60)
    if r.exit_code != 0:
        raise RuntimeError(f"git add 失败：{r.output[:500]}")
    names = sandbox.run("git -c core.quotepath=off diff --cached --no-renames --name-only HEAD", timeout=60)
    if names.exit_code != 0:
        raise RuntimeError(f"git diff 失败：{names.output[:500]}")
    patch = sandbox.run("git -c core.quotepath=off diff --cached --no-renames --binary --no-color --no-ext-diff HEAD", timeout=60)
    if patch.exit_code != 0:
        raise RuntimeError(f"git diff 失败：{patch.output[:500]}")
    return patch.output, [line for line in names.output.splitlines() if line.strip()]


def apply_patch(sandbox: Sandbox, patch: str) -> str:
    """把 patch 打到干净的工作区。成功返回空字符串，失败返回错误信息。"""
    path = ".nanocoder-fix.patch"
    sandbox.write_file(path, patch)
    r = sandbox.run(f"git apply --binary {path} 2>&1; code=$?; rm -f {path}; exit $code", timeout=60)
    return "" if r.exit_code == 0 else (r.output.strip()[:500] or f"git apply exited {r.exit_code}")


def get_patch(sandbox: Sandbox) -> str:
    r = sandbox.run(_ADD_NEW_FILES, timeout=60)
    if r.exit_code != 0:
        raise RuntimeError(f"git add -N 失败：{r.output[:500]}")
    cmd = "git -c core.quotepath=off diff --no-color --no-ext-diff -- . " + " ".join(EXCLUDE_PATHSPECS)
    result = sandbox.run(cmd, timeout=60)
    if result.exit_code != 0:
        raise RuntimeError(f"git diff 失败：{result.output[:500]}")
    return result.output
