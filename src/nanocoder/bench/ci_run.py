"""M1：在 CI 修复评测集上运行。需要 docker，会调模型。

    python -m nanocoder.bench.ci_run --run-id ci-base --work ~/ciset --dry-run   # 只列任务和预算
    python -m nanocoder.bench.ci_run --run-id ci-base --work ~/ciset --max-total-input 4000000

每题都走 cifix.fix_ci，和产品一模一样；不给 CI 日志（历史日志多半已过期），只用本地复现的输出。
“变绿”不等于修对，所以每题保存 agent 和人写的 diff，供人工对照。

产物在 runs/<run_id>/：results.jsonl、<id>/（report.md、fix.patch 或 rejected.patch、gold.diff、before.txt、after.txt、trace、messages）。
已有结果的题会跳过；--retry-errors 重跑基础设施失败的题，被替换的结果移到 discarded.jsonl，花的 token 仍计入预算。
开始新一题前，如果“已花 + 单题上限”超过预算就停下，所以不会超支。
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

from miniagent.config import load_settings
from miniagent.console import setup_console

from .. import CODINGAGENT_ROOT
from ..cifix.__main__ import build_agent, fingerprint, write_artifacts
from ..cifix.config import parse_config
from ..cifix.env import DockerEnv
from ..cifix.runner import fix_ci

TASKS = CODINGAGENT_ROOT / "benchmarks" / "ciset" / "tasks.jsonl"
RUNS = CODINGAGENT_ROOT / "runs"
EVIDENCE_OF_INFRA = ("llm_error",)
INFRA_STATUSES = ("harness_error", "setup_failed")
TOKEN_FIELDS = ("prompt_tokens", "cached_tokens", "completion_tokens")


def _retry(command: list[str], timeout: float, tries: int = 4) -> subprocess.CompletedProcess:
    """WSL 到 GitHub 的 TLS 连接时常被断开，网络命令重试几次。"""
    for attempt in range(tries):
        try:
            return subprocess.run(command, capture_output=True, check=True, timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def checkout(work: Path, repo: str, base: str, fix: str) -> Path:
    """每个仓库一份裸克隆，按需取提交（PR 的提交可能只在 refs/pull 下）。本地已有就不再联网。"""
    bare = work / "repos" / (repo.replace("/", "__") + ".git")
    if not bare.exists():
        bare.parent.mkdir(parents=True, exist_ok=True)
        _retry(["git", "clone", "-q", "--bare", "--filter=blob:none", f"https://github.com/{repo}.git", str(bare)], timeout=900)
    have = all(subprocess.run(["git", "-C", str(bare), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True).returncode == 0 for sha in (base, fix))
    if not have:
        _retry(["git", "-C", str(bare), "fetch", "-q", "origin", base, fix], timeout=600)
    return bare


def materialize(bare: Path, sha: str, dest: Path) -> None:
    """dest 成为一个 HEAD 在 sha、只有这一个提交的独立仓库。blob 是按需下载的，也要重试。"""
    dest.mkdir(parents=True)
    tar = _retry(["git", "-C", str(bare), "archive", sha], timeout=600)
    subprocess.run(["tar", "-xf", "-", "-C", str(dest)], input=tar.stdout, check=True)
    subprocess.run(
        "git init -q && git add -A -f && git -c user.name=t -c user.email=t@example.com commit -q -m base",
        shell=True, cwd=dest, check=True,
    )  # fmt: skip


def load_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def is_infra_failure(record: dict[str, Any]) -> bool:
    return record["status"] in INFRA_STATUSES or record.get("exit_reason") in EVIDENCE_OF_INFRA


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """比例的 95% Wilson 区间。"""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def write_outputs(out: Path, name: str, results: list[Any]) -> None:
    """保存检查的完整输出，用来核对闸门判定和研究日志截取。"""
    text = "\n".join(f"===== {r.name} exit={r.exit_code} timed_out={r.timed_out} command={r.command}\n{r.output}" for r in results)
    (out / name).write_text(text, encoding="utf-8", errors="replace")


def run_task(task: dict[str, Any], settings: Any, work: Path, run_dir: Path, effort: str) -> dict[str, Any]:
    out = run_dir / task["id"]
    out.mkdir(parents=True, exist_ok=True)
    config = parse_config(task["config"])
    (out / "gold.diff").write_text(task["gold_diff"], encoding="utf-8", newline="")
    bare = checkout(work, task["repo"], task["base"], task["fix"])
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        repo = Path(tmp) / "repo"
        materialize(bare, task["base"], repo)
        agent = build_agent(settings, config, effort, out / "trace.jsonl")
        outcome = fix_ci(DockerEnv(repo, config), config, agent)
    digest, payload = fingerprint(config, settings.model, effort)
    write_artifacts(out, outcome, task["base"], settings.model, digest, payload)
    write_outputs(out, "before.txt", outcome.before)
    write_outputs(out, "after.txt", outcome.after)
    a = outcome.agent
    return {
        "id": task["id"], "repo": task["repo"], "pr": task["pr"], "kind": task.get("kind"), "status": outcome.status, "detail": outcome.detail[:300],
        "before": {r.name: r.exit_code for r in outcome.before}, "after": {r.name: r.exit_code for r in outcome.after},
        "before_chars": {r.name: len(r.output) for r in outcome.before}, "tool_calls": a.tool_calls if a else 0, "tool_errors": a.tool_errors if a else 0,
        "reasoning_tokens": a.reasoning_tokens if a else 0,
        "changed_files": outcome.changed_files, "gold_files": task["files"],
        "same_files": sorted(outcome.changed_files) == sorted(task["files"]),
        "exit_reason": a.exit_reason if a else None, "steps": a.steps if a else 0,
        "prompt_tokens": a.prompt_tokens if a else 0, "cached_tokens": a.cached_tokens if a else 0,
        "completion_tokens": a.completion_tokens if a else 0, "wall_time": round(a.wall_time, 1) if a else 0,
        "error": a.error if a else None, "model": settings.model, "fingerprint": digest,
    }  # fmt: skip


def summarize(records: list[dict[str, Any]], discarded: list[dict[str, Any]]) -> None:
    valid = [r for r in records if not is_infra_failure(r)]
    fixed = [r for r in valid if r["status"] == "fixed"]
    low, high = wilson(len(fixed), len(valid))
    print(f"\n有效 {len(valid)} 题，变绿 {len(fixed)} 题（{len(fixed) / max(len(valid), 1):.1%}，95% Wilson 区间 {low:.0%}～{high:.0%}）；基础设施失败 {len(records) - len(valid)} 题")
    print("结果分布：", dict(Counter(r["status"] for r in records)))
    print("结束原因：", dict(Counter(r["exit_reason"] for r in records)))
    for kind in sorted({r.get("kind") or "?" for r in valid}):
        group = [r for r in valid if (r.get("kind") or "?") == kind]
        print(f"  {kind}: {sum(r['status'] == 'fixed' for r in group)}/{len(group)}")
    totals = {k: sum(r[k] for r in records + discarded) for k in TOKEN_FIELDS}
    print(f"累计输入 {totals['prompt_tokens']:,}（缓存 {totals['cached_tokens']:,}），输出 {totals['completion_tokens']:,}；其中被替换的结果 {len(discarded)} 条")
    print(f"变绿且改的文件和人一致：{sum(r['same_files'] for r in fixed)}/{len(fixed)}")


def main() -> int:
    setup_console()
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--work", type=Path, required=True, help="放克隆的目录，放在项目外")
    p.add_argument("--tasks", type=Path, default=TASKS)
    p.add_argument("--limit", type=int)
    p.add_argument("--reasoning-effort", default="high", choices=["low", "medium", "high"])
    p.add_argument("--max-total-input", type=int, default=4_000_000, help="累计输入 token 预算，含被替换的结果")
    p.add_argument("--retry-errors", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    tasks = [json.loads(x) for x in args.tasks.read_text(encoding="utf-8").splitlines() if x.strip()]
    if args.limit:
        tasks = tasks[: args.limit]
    work = args.work.expanduser()
    work.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    discarded_path = run_dir / "discarded.jsonl"
    records = load_results(results_path)
    if args.retry_errors:
        with discarded_path.open("a", encoding="utf-8") as f:
            for r in records:
                if is_infra_failure(r):
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        records = [r for r in records if not is_infra_failure(r)]
        results_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    discarded = load_results(discarded_path)
    done = {r["id"] for r in records}
    pending = [t for t in tasks if t["id"] not in done]
    print(f"共 {len(tasks)} 题，待跑 {len(pending)} 题；累计输入上限 {args.max_total_input:,}")
    if args.dry_run:
        for t in pending:
            print(f"  {t['id']}  {t['lines']} 行  {t['fix_message'][:60]}")
        return 0

    settings = load_settings()
    for task in pending:
        spent = sum(r["prompt_tokens"] for r in records + discarded)
        task_limit = parse_config(task["config"]).limits.max_input_tokens
        if spent + task_limit > args.max_total_input:
            print(f"⛔ 累计输入 {spent:,}，再跑一题可能超过预算 {args.max_total_input:,}，停止。结果已保存，加大 --max-total-input 可续跑")
            break
        print(f"=== {task['id']}", flush=True)
        try:
            record = run_task(task, settings, work, run_dir, args.reasoning_effort)
        except Exception as e:
            (run_dir / task["id"]).mkdir(parents=True, exist_ok=True)
            (run_dir / task["id"] / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            record = {
                "id": task["id"], "repo": task["repo"], "pr": task["pr"], "kind": task.get("kind"), "status": "harness_error", "detail": f"{type(e).__name__}: {e}"[:300],
                "changed_files": [], "gold_files": task["files"], "same_files": False, "exit_reason": None, "steps": 0,
                "prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0, "wall_time": 0, "error": str(e)[:300],
                "model": settings.model, "fingerprint": "",
            }  # fmt: skip
        records.append(record)
        with results_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"  {record['status']} steps={record['steps']} in={record['prompt_tokens']:,} {record['detail'][:120]}", flush=True)
        # 额度用完不会被重试，后面每题都会白搭环境
        if "HTTP 403" in (record.get("error") or ""):
            print("⛔ 中转站返回 403（额度不足或无权限），停止。处理后用 --retry-errors 续跑")
            break
    summarize(records, discarded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
