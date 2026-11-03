"""把已合并的真实 PR 做成回放任务：合并前的代码 + issue + PR 自带的测试（隐藏）。

    python benchmarks/build_realpr.py --out ~/realpr/tasks   # 在 WSL 里运行，仓库较大，不放进项目目录
    NANOCODER_BENCH_DIR=~/realpr/tasks <任务 venv>/bin/python -m nanocoder.bench --suite realpr ...

每个任务要在装了该仓库依赖的 venv 里运行（沙箱里的 python 就是运行 nanocoder 的 python）。

- *_orig：issue 原文。lighthouse 和 MobileWorld 的 issue 是定位到原因后才写的，已经写明文件和修法，
  只能说明 agent 能照着做。
- *_symptom：只描述现象的版本，由回放时另写，才真正考验定位。
- MobileAgent 的 issue 由第三方提交，只描述了现象。PR 的测试还检查了错误信息的措辞和 issue 没提到的
  兼容格式（\\r\\n、缺闭合标签等），所以这一题的通过数不等于修复质量，要结合 patch 看。
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISSUES = HERE / "realpr_src"
PR_REPOS = Path("/mnt/e/zlf/project/github_pr")

LIGHTHOUSE_SYMPTOM = """# Predictors crash when loading pre-trained checkpoints

After upgrading PyTorch to 2.6, loading any released checkpoint through the predictors in `lighthouse.models` fails:

```
_pickle.UnpicklingError: Weights only load failed. ...
WeightsUnpickler error: Unsupported global: GLOBAL easydict.EasyDict was not an allowed global by default.
```

It worked on older PyTorch versions. CI still passes. Predictors should be able to load the released checkpoints.
"""

MOBILEWORLD_SYMPTOM = """# Language breakdown in the log viewer doesn't add up

When I filter tasks by language tag in the log viewer, the `lang-en` and `lang-cn` counts together are smaller than the \
total number of registered tasks, so some tasks never show up under any language filter. \
Every task is supposed to belong to exactly one language.
"""

SPECS = [
    {
        "id": "rp_lighthouse", "repo": "lighthouse", "base": "3e841d3", "head": "802b727",
        "tests": ["tests/test_models.py"],
        "f2p": ["tests/test_models.py::test_load_checkpoint_with_easydict_opt"], "p2p": [],
        "variants": {"orig": (ISSUES / "lighthouse_issue.md").read_text(encoding="utf-8"), "symptom": LIGHTHOUSE_SYMPTOM},
    },
    {
        "id": "rp_mobileworld", "repo": "MobileWorld", "base": "eb98513", "head": "4881a25",
        "tests": ["tests/tasks/test_task_tags.py"],
        "f2p": ["tests/tasks/test_task_tags.py::test_every_task_has_exactly_one_language_tag"], "p2p": [],
        "variants": {"orig": (ISSUES / "mobileworld_issue.md").read_text(encoding="utf-8"), "symptom": MOBILEWORLD_SYMPTOM},
    },
    {
        "id": "rp_mobileagent", "repo": "MobileAgent", "base": "81fa28b", "head": "0b5c25a",
        "tests": ["Mobile-Agent-v3.5/mobile_use/test_parse_action.py"],
        "f2p": [
            f"Mobile-Agent-v3.5/mobile_use/test_parse_action.py::ParseActionTest::{t}"
            for t in (
                "test_arguments_without_action_raises_value_error", "test_broken_json_raises_value_error",
                "test_empty_output_raises_value_error", "test_json_without_arguments_raises_value_error",
                "test_missing_closing_tag_is_tolerated", "test_missing_tool_call_tag_raises_value_error",
                "test_tags_without_newlines_and_surrounding_text", "test_windows_line_endings",
            )
        ],
        "p2p": [],
        "variants": {"orig": (ISSUES / "mobileagent_issue.md").read_text(encoding="utf-8")},
    },
]  # fmt: skip


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def build(spec: dict, variant: str, issue: str, out: Path) -> None:
    src = PR_REPOS / spec["repo"]
    task = out / f"{spec['id']}_{variant}"
    if task.exists():
        shutil.rmtree(task)
    (task / "repo").mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(git(src, "archive", spec["base"]))) as tar:
        tar.extractall(task / "repo", filter="data")
    for t in spec["tests"]:
        dst = task / "hidden_tests" / t
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(git(src, "show", f"{spec['head']}:{t}"))
    gold = git(src, "diff", spec["base"], spec["head"], "--", ".", *(f":(exclude){t}" for t in spec["tests"]))
    (task / "gold.diff").write_bytes(gold)
    meta = {
        "id": task.name, "category": variant, "repo": spec["repo"], "issue": issue,
        "fail_to_pass": spec["f2p"], "pass_to_pass": spec["p2p"],
    }  # fmt: skip
    (task / "task.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(task.name, f"{len(gold)} bytes of gold diff")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    out = Path(p.parse_args().out).expanduser() / "realpr"
    for spec in SPECS:
        for variant, issue in spec["variants"].items():
            build(spec, variant, issue, out)


if __name__ == "__main__":
    main()
