"""批量运行 + 评测。

    python -m nanocoder.bench --validate                  # 校验玩具任务本身（不调模型）
    python -m nanocoder.bench --suite toy --run-id m0     # 跑全部玩具任务
    python -m nanocoder.bench --suite toy --tasks toy01_paginate -v   # 单题，终端打印每一步
    python -m nanocoder.bench --suite toy --run-id m0 --k 3           # 每题跑 3 次，算 pass^3
    python -m nanocoder.bench --suite hard --validate                 # hard 套件（隐藏测试）

产物在 runs/<run_id>/：config.json、results.jsonl、traces/、messages/、patches/。
同一个 run_id 再跑一次会跳过已完成的 (任务, 第几次)，可以断点续跑。
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import threading
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from miniagent.config import ConfigError, load_settings
from miniagent.console import setup_console
from miniagent.llm import LLM
from miniagent.trace import Tracer

from .. import CODINGAGENT_ROOT
from ..agent import AgentConfig, CodingAgent
from ..patch import get_patch
from ..prompts import PROMPT_VERSION, SYSTEM_PROMPTS
from ..sandbox import LocalSandbox
from .evaluate import evaluate_patch, validate_task
from .tasks import SUITES, Task, load_tasks

RUNS_DIR = CODINGAGENT_ROOT / "runs"
_lock = threading.Lock()


def run_one(task: Task, attempt: int, llm: LLM, cfg: AgentConfig, run_dir: Path, verbose: bool) -> dict[str, Any]:
    name = f"{task.id}__{attempt}"
    tracer = Tracer(log_dir=run_dir / "traces", echo=verbose, max_summary_chars=20_000)
    tracer.path = tracer.log_dir / f"{name}.jsonl"
    if tracer.path.exists():
        tracer.path.unlink()  # 上次中断留下的半截 trace
    record: dict[str, Any] = {"instance_id": task.id, "attempt": attempt, "category": task.category}
    try:
        with LocalSandbox(task.repo_dir) as sb:
            result = CodingAgent(llm, cfg, tracer).run(task.issue, sb)
            patch = get_patch(sb)
        ev = evaluate_patch(task, patch)
        _write(run_dir / "patches" / f"{name}.diff", patch)
        _write(run_dir / "messages" / f"{name}.json", json.dumps(result.messages, ensure_ascii=False, indent=1))
        _write(run_dir / "eval_logs" / f"{name}.log", ev.log)
        record.update(
            resolved=ev.resolved,
            patch_applied=ev.patch_applied,
            f2p_passed=ev.f2p_passed,
            p2p_passed=ev.p2p_passed,
            exit_reason=result.exit_reason,
            steps=result.steps,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cached_tokens=result.cached_tokens,
            cost=round(result.cost, 6),
            wall_time=round(result.wall_time, 1),
            tool_calls=result.tool_calls,
            tool_errors=result.tool_errors,
            unverified_submit=result.unverified_submit,
            patch_lines=patch.count("\n"),
            error=result.error,
        )
    except Exception as e:  # 单题出错不影响整批
        record.update(resolved=False, exit_reason="harness_error", error=f"{type(e).__name__}: {e}")
        _write(run_dir / "eval_logs" / f"{name}.error", traceback.format_exc())
    record["trace_path"] = str(tracer.path.relative_to(CODINGAGENT_ROOT))
    return record


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_results(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "results.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize(results: list[dict[str, Any]], k: int) -> str:
    if not results:
        return "（没有结果）"
    by_task: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_task[r["instance_id"]].append(r)
    n = len(results)
    resolved = sum(r.get("resolved", False) for r in results)
    lines = [
        f"运行次数 {n}（{len(by_task)} 题 × 最多 {k} 次）",
        f"解决率 pass@1（所有运行的平均）：{resolved}/{n} = {resolved / n:.1%}",
    ]
    full = [rs for rs in by_task.values() if len(rs) >= k]
    if k > 1 and full:
        all_ok = sum(all(r.get("resolved") for r in rs) for rs in full)
        lines.append(f"pass^{k}（{k} 次都成功）：{all_ok}/{len(full)} = {all_ok / len(full):.1%}")

    def avg(key: str) -> float:
        vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
        return sum(vals) / len(vals) if vals else 0.0

    lines += [
        f"平均步数 {avg('steps'):.1f}，平均 token 输入 {avg('prompt_tokens'):,.0f} / 输出 {avg('completion_tokens'):,.0f}",
        f"单题平均成本 ${avg('cost'):.4f}（估算），总成本 ${sum(r.get('cost', 0) for r in results):.3f}，平均耗时 {avg('wall_time'):.0f}s",
        f"工具调用 {sum(r.get('tool_calls', 0) for r in results)} 次，其中出错 {sum(r.get('tool_errors', 0) for r in results)} 次；"
        f"未验证就提交 {sum(bool(r.get('unverified_submit')) for r in results)} 次",
        "结束原因：" + "，".join(f"{k_}={v}" for k_, v in Counter(r.get("exit_reason") for r in results).most_common()),
    ]
    cats: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        cats[r.get("category") or "-"].append(bool(r.get("resolved")))
    lines.append("按类别：" + "，".join(f"{c} {sum(v)}/{len(v)}" for c, v in sorted(cats.items())))
    failed = sorted({r["instance_id"] for r in results if not r.get("resolved")})
    if failed:
        lines.append("未解决：" + ", ".join(failed))
    return "\n".join(lines)


def main() -> int:
    setup_console()
    p = argparse.ArgumentParser(description="nanocoder 评测")
    p.add_argument("--suite", default="toy", choices=SUITES)
    p.add_argument("--tasks", help="逗号分隔的任务 id，默认全部")
    p.add_argument("--validate", action="store_true", help="只校验任务本身（参考答案能通过、原始代码会失败），不调模型")
    p.add_argument("--run-id", help="默认按时间生成")
    p.add_argument("--k", type=int, default=1, help="每题重复次数")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=AgentConfig.max_steps)
    p.add_argument("--cost-limit", type=float, default=AgentConfig.cost_limit, help="单题成本上限（美元）")
    p.add_argument("--reasoning-effort", default="none", help="gpt-6-luna 在 chat/completions 下用工具必须是 none")
    p.add_argument("--prompt", default=PROMPT_VERSION, choices=sorted(SYSTEM_PROMPTS), help="系统提示词版本（消融用）")
    p.add_argument("-v", "--verbose", action="store_true", help="终端打印每一步（建议配合 --workers 1）")
    args = p.parse_args()

    ids = [t.strip() for t in args.tasks.split(",")] if args.tasks else None
    tasks = load_tasks(args.suite, ids=ids)

    if args.validate:
        bad = 0
        for t in tasks:
            problems = validate_task(t)
            print(f"{'✅' if not problems else '❌'} {t.id}")
            for prob in problems:
                print("    " + prob.replace("\n", "\n    "))
            bad += bool(problems)
        print(f"\n{len(tasks) - bad}/{len(tasks)} 个任务合格")
        return 1 if bad else 0

    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"❌ 配置错误：\n{e}")
        return 1
    effort = None if args.reasoning_effort in ("", "omit") else args.reasoning_effort
    settings = dataclasses.replace(settings, reasoning_effort=effort, timeout=180.0)
    llm = LLM(settings)
    cfg = AgentConfig(max_steps=args.max_steps, cost_limit=args.cost_limit, prompt=args.prompt)

    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "suite": args.suite,
        "model": settings.model,
        "reasoning_effort": effort,
        "prompt_version": args.prompt,
        "agent": dataclasses.asdict(cfg),
        "k": args.k,
    }
    config_path = run_dir / "config.json"
    if config_path.exists() and json.loads(config_path.read_text(encoding="utf-8")) != config:
        print(f"❌ runs/{run_id} 已存在且配置不同，换一个 --run-id，避免把两种配置的结果混在一起")
        return 1
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    done = {(r["instance_id"], r["attempt"]) for r in load_results(run_dir)}
    todo = [(t, a) for a in range(1, args.k + 1) for t in tasks if (t.id, a) not in done]
    print(f"run_id={run_id}  模型={settings.model}  待跑 {len(todo)} 次（已完成 {len(done)}）")

    results_path = run_dir / "results.jsonl"
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(run_one, t, a, llm, cfg, run_dir, args.verbose): (t, a) for t, a in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            with _lock, results_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            mark = "✅" if rec.get("resolved") else "❌"
            print(
                f"[{i}/{len(todo)}] {mark} {rec['instance_id']}#{rec['attempt']}  "
                f"{rec.get('exit_reason')}  steps={rec.get('steps', '-')}  ${rec.get('cost', 0):.4f}"
                + (f"  {rec['error'][:120]}" if rec.get("error") else "")
            )

    print("\n" + summarize(load_results(run_dir), args.k))
    return 0


if __name__ == "__main__":
    sys.exit(main())
