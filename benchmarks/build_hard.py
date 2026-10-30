"""根据 <suite>_src/specs.py 生成任务集：benchmarks/<suite>/<id>/。

    python benchmarks/build_hard.py                 # hard（v1），会先删掉 benchmarks/hard/
    python benchmarks/build_hard.py --suite hard2   # hard2（v2）

每个任务目录：
- repo/          基础仓库 + 注入的 bug，不含隐藏测试（agent 看到的就是它）
- solution/      被改动文件的原始版本（参考答案，只用于 --validate）
- hidden_tests/  隐藏测试，评测时才覆盖进仓库
- task.json      issue、FAIL_TO_PASS、PASS_TO_PASS

生成后用 `python -m nanocoder.bench --suite hard --validate` 校验。
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")


def test_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]


def build_one(spec: dict, SRC: Path, OUT: Path) -> None:
    task_dir = OUT / spec["id"]
    repo_src = SRC / "repos" / spec["repo"]
    hidden_src = SRC / "hidden" / spec["id"]
    repo = task_dir / "repo"
    shutil.copytree(repo_src, repo, ignore=IGNORE)

    for rel, old, new in spec["mutations"]:
        path = repo / rel
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{spec['id']}: 在 {rel} 里找到 {count} 处要替换的代码（应为 1）：\n{old}")
        solution_file = task_dir / "solution" / rel
        if not solution_file.exists():
            solution_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo_src / rel, solution_file)
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    if not hidden_src.exists():
        raise SystemExit(f"{spec['id']}: 缺少隐藏测试 {hidden_src}")
    shutil.copytree(hidden_src, task_dir / "hidden_tests", ignore=IGNORE)

    f2p, p2p = [], []
    for test_file in sorted((task_dir / "hidden_tests").rglob("test_*.py")):
        rel = test_file.relative_to(task_dir / "hidden_tests").as_posix()
        if (repo / rel).exists():
            raise SystemExit(f"{spec['id']}: 隐藏测试 {rel} 和仓库里的文件重名")
        for name in test_names(test_file):
            (f2p if name in spec["f2p"] else p2p).append(f"{rel}::{name}")
    missing = set(spec["f2p"]) - {t.split("::")[1] for t in f2p}
    if missing:
        raise SystemExit(f"{spec['id']}: f2p 里的测试在隐藏测试文件中不存在：{sorted(missing)}")
    visible = sorted(p.relative_to(repo).as_posix() for p in (repo / "tests").rglob("test_*.py"))

    meta = {
        "id": spec["id"],
        "category": spec["category"],
        "repo": spec["repo"],
        "issue": spec["issue"],
        "fail_to_pass": f2p,
        "pass_to_pass": visible + p2p,
    }
    (task_dir / "task.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--suite", default="hard", choices=["hard", "hard2"])
    suite = p.parse_args().suite
    SRC, OUT = HERE / f"{suite}_src", HERE / suite
    sys.path.insert(0, str(SRC))
    from specs import TASKS  # noqa: E402

    ids = [t["id"] for t in TASKS]
    if len(ids) != len(set(ids)):
        raise SystemExit("任务 id 重复")
    if OUT.exists():
        shutil.rmtree(OUT)
    for spec in TASKS:
        build_one(spec, SRC, OUT)
        print(f"built {spec['id']}")
    print(f"\n{len(TASKS)} 个任务 -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
