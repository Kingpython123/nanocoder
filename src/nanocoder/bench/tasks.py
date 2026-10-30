"""任务定义与加载。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .. import CODINGAGENT_ROOT

BENCH_DIR = CODINGAGENT_ROOT / "benchmarks"
SUITES = ("toy", "hard", "hard2")  # benchmarks/<suite>/<id>/task.json
TOY_DIR = BENCH_DIR / "toy"


@dataclass
class Task:
    id: str
    issue: str
    repo_dir: Path
    fail_to_pass: list[str]
    pass_to_pass: list[str]
    category: str = ""
    solution_dir: Path | None = None  # 参考答案（覆盖到 repo 上的文件），只用于校验任务本身
    hidden_tests_dir: Path | None = None  # 隐藏测试：agent 看不到，评测时才覆盖进仓库（hard 套件）
    extra: dict = field(default_factory=dict)


def load_tasks(suite: str = "toy", ids: list[str] | None = None) -> list[Task]:
    if suite not in SUITES:
        raise ValueError(f"未知任务集 {suite!r}，可选：{', '.join(SUITES)}")
    return load_toy_tasks(BENCH_DIR / suite, ids)


def load_toy_tasks(root: Path = TOY_DIR, ids: list[str] | None = None) -> list[Task]:
    tasks = []
    for meta_path in sorted(root.glob("*/task.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if ids and meta["id"] not in ids:
            continue
        base = meta_path.parent
        tasks.append(
            Task(
                id=meta["id"],
                issue=meta["issue"],
                repo_dir=base / "repo",
                fail_to_pass=meta["fail_to_pass"],
                pass_to_pass=meta["pass_to_pass"],
                category=meta.get("category", ""),
                solution_dir=base / "solution" if (base / "solution").exists() else None,
                hidden_tests_dir=base / "hidden_tests" if (base / "hidden_tests").exists() else None,
            )
        )
    if ids:
        missing = set(ids) - {t.id for t in tasks}
        if missing:
            raise ValueError(f"找不到任务：{', '.join(sorted(missing))}")
    return tasks
