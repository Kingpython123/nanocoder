"""M2：在 SWE-bench Verified 子集上运行 + 官方评测。需要在 Linux（WSL2）里、能用 docker 的环境运行。

    python -m nanocoder.bench.swebench_run --subset verified50 --run-id swe-base --dry-run
    python -m nanocoder.bench.swebench_run --subset verified50 --run-id swe-base --limit 1
    python -m nanocoder.bench.swebench_run --subset verified50 --run-id swe-e7e8 \
        --api responses --reasoning-effort high --prompt v2_spec

流程按批进行（每批 --batch 题），控制磁盘占用（每个任务镜像约 4GB）：
1. 拉取这一批任务的官方镜像（swebench/sweb.eval.x86_64.*，数据集的 image 字段）；
2. agent 在镜像里的 DockerSandbox 中工作（断网），用 git diff 取 patch，写入 predictions.jsonl；
3. 用官方 harness（swebench.harness.run_evaluation）评测这一批，读报告得到 resolved；
4. 删掉这一批的镜像（--keep-images 可以保留）。

产物在 runs/<run_id>/：config.json、predictions.jsonl、results.jsonl（含 resolved，可直接用 compare 配对比较）、
traces/、messages/、patches/、harness/（官方评测的日志和报告）。断点续跑：已有结果的题会跳过。
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from miniagent.config import ConfigError, load_settings
from miniagent.console import setup_console
from miniagent.llm import LLM
from miniagent.trace import Tracer

from .. import CODINGAGENT_ROOT
from ..agent import AgentConfig, CodingAgent
from ..docker_sandbox import DockerSandbox
from ..patch import get_patch
from ..prompts import PROMPT_VERSION, SYSTEM_PROMPTS
from ..responses_llm import ResponsesLLM
from .__main__ import RUNS_DIR, _write, drop_infra_failures, load_results, summarize

DATASET = "SWE-bench/SWE-bench_Verified"
SUBSET_DIR = CODINGAGENT_ROOT / "benchmarks" / "swebench"
# 长任务（50+ 步）中途遇到中转站 429 就丢掉整次运行太亏：重试 8 次，退避 2..256 秒（共约 8.5 分钟）
LLM_RETRY = {"max_retries": 8, "retry_backoff": 2.0}
_lock = threading.Lock()


def load_instances(subset: str) -> list[dict[str, Any]]:
    from datasets import load_dataset

    ids = [line.strip() for line in (SUBSET_DIR / f"{subset}.txt").read_text(encoding="utf-8").splitlines()]
    ids = [i for i in ids if i and not i.startswith("#")]
    by_id = {row["instance_id"]: row for row in load_dataset(DATASET, split="test")}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"数据集里找不到：{', '.join(missing)}")
    return [by_id[i] for i in ids]


def docker(*args: str, timeout: float = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def pull(image: str, tries: int = 4) -> None:
    """Docker Hub 偶尔在认证阶段断开（EOF），重试几次。"""
    if docker("image", "inspect", image, timeout=60).returncode == 0:
        return
    for attempt in range(tries):
        r = docker("pull", "-q", image)
        if r.returncode == 0:
            return
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"拉取镜像失败：{image}：{r.stderr.strip()[:300]}")


def run_agent(inst: dict[str, Any], llm: Any, cfg: AgentConfig, run_dir: Path, model_name: str) -> dict[str, Any]:
    iid = inst["instance_id"]
    tracer = Tracer(log_dir=run_dir / "traces", echo=False, max_summary_chars=20_000)
    tracer.path = tracer.log_dir / f"{iid}.jsonl"
    if tracer.path.exists():
        tracer.path.unlink()
    record: dict[str, Any] = {"instance_id": iid, "attempt": 1, "category": inst["repo"], "difficulty": inst.get("difficulty"), "model": model_name}
    patch = ""
    try:
        pull(inst["image"])
        with DockerSandbox.for_swebench(inst["image"]) as sb:
            result = CodingAgent(llm, cfg, tracer).run(inst["problem_statement"], sb)
            patch = get_patch(sb)
        _write(run_dir / "patches" / f"{iid}.diff", patch)
        _write(run_dir / "messages" / f"{iid}.json", json.dumps(result.messages, ensure_ascii=False, indent=1))
        record.update(
            exit_reason=result.exit_reason,
            steps=result.steps,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cached_tokens=result.cached_tokens,
            reasoning_tokens=result.reasoning_tokens,
            cost=round(result.cost, 6),
            wall_time=round(result.wall_time, 1),
            tool_calls=result.tool_calls,
            tool_errors=result.tool_errors,
            unverified_submit=result.unverified_submit,
            patch_lines=patch.count("\n"),
            error=result.error,
        )
    except Exception as e:
        record.update(exit_reason="harness_error", error=f"{type(e).__name__}: {e}")
        _write(run_dir / "eval_logs" / f"{iid}.error", traceback.format_exc())
    with _lock, (run_dir / "predictions.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"instance_id": iid, "model_name_or_path": model_name, "model_patch": patch}) + "\n")
    return record


def evaluate_batch(ids: list[str], run_dir: Path, run_id: str, workers: int) -> set[str]:
    """用官方 harness 评测这一批，返回 resolved 的 instance_id。"""
    harness_dir = run_dir / "harness"
    harness_dir.mkdir(exist_ok=True)
    preds = latest_predictions(run_dir)
    batch_preds = harness_dir / f"preds_{ids[0]}.jsonl"
    batch_preds.write_text("".join(json.dumps(preds[i]) + "\n" for i in ids if i in preds), encoding="utf-8")
    cmd = [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "-d", DATASET, "-p", str(batch_preds), "-i", *ids,
        "-id", run_id, "--max_workers", str(workers), "--report_dir", str(harness_dir),
    ]  # fmt: skip
    r = subprocess.run(cmd, cwd=harness_dir, capture_output=True, text=True, timeout=3 * 3600)
    (harness_dir / f"eval_{ids[0]}.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    resolved: set[str] = set()
    for iid in ids:  # 每题的 report.json：logs/run_evaluation/<run_id>/<model>/<iid>/report.json
        for report in harness_dir.glob(f"logs/run_evaluation/{run_id}/*/{iid}/report.json"):
            data = json.loads(report.read_text(encoding="utf-8"))
            if data.get(iid, {}).get("resolved"):
                resolved.add(iid)
    return resolved


def latest_predictions(run_dir: Path) -> dict[str, dict]:
    path = run_dir / "predictions.jsonl"
    preds: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                p = json.loads(line)
                preds[p["instance_id"]] = p  # 重跑过的题以最后一次为准
    return preds


def main() -> int:
    setup_console()
    p = argparse.ArgumentParser(description="nanocoder × SWE-bench Verified")
    p.add_argument("--subset", default="verified50", help="benchmarks/swebench/<subset>.txt")
    p.add_argument("--run-id", required=True)
    p.add_argument("--limit", type=int, help="只跑前 N 题（冒烟测试）")
    p.add_argument("--batch", type=int, default=6, help="每批题数（控制磁盘：每题镜像约 4GB）")
    p.add_argument("--workers", type=int, default=2, help="同时跑的 agent 数")
    p.add_argument("--eval-workers", type=int, default=2)
    p.add_argument("--max-steps", type=int, default=60)
    p.add_argument("--cost-limit", type=float, default=1.0)
    p.add_argument("--api", default="chat", choices=["chat", "responses"])
    p.add_argument("--reasoning-effort", default="none")
    p.add_argument("--prompt", default=PROMPT_VERSION, choices=sorted(SYSTEM_PROMPTS))
    p.add_argument("--keep-images", action="store_true")
    p.add_argument("--retry-errors", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="只列出要跑的题，不调模型")
    args = p.parse_args()

    instances = load_instances(args.subset)[: args.limit]
    run_dir = RUNS_DIR / args.run_id
    if args.dry_run:
        for inst in instances:
            print(inst["instance_id"], inst["repo"], inst.get("difficulty"))
        print(f"{len(instances)} 题")
        return 0

    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"❌ 配置错误：\n{e}")
        return 1
    effort = None if args.reasoning_effort in ("", "omit") else args.reasoning_effort
    settings = dataclasses.replace(settings, reasoning_effort=effort, timeout=300.0)
    if args.api == "responses":
        llm: Any = ResponsesLLM(settings, reasoning_effort=effort if effort not in (None, "none") else "medium", **LLM_RETRY)
        effort = llm.reasoning_effort
    else:
        llm = LLM(settings, **LLM_RETRY)
    cfg = AgentConfig(max_steps=args.max_steps, cost_limit=args.cost_limit, wall_timeout=1800, prompt=args.prompt)
    model_name = f"nanocoder__{settings.model}__{args.api}-{effort}__{args.prompt}"

    run_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "suite": f"swebench:{args.subset}",
        "model": settings.model,
        "api": args.api,
        "reasoning_effort": effort,
        "prompt_version": args.prompt,
        "agent": dataclasses.asdict(cfg),
    }
    config_path = run_dir / "config.json"
    if config_path.exists() and json.loads(config_path.read_text(encoding="utf-8")) != config:
        print(f"❌ runs/{args.run_id} 已存在且配置不同，换一个 --run-id")
        return 1
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.retry_errors:
        drop_infra_failures(run_dir)

    done = {r["instance_id"] for r in load_results(run_dir)}
    todo = [i for i in instances if i["instance_id"] not in done]
    print(f"run_id={args.run_id}  model={model_name}  待跑 {len(todo)} 题（已完成 {len(done)}）")

    for start in range(0, len(todo), args.batch):
        batch = todo[start : start + args.batch]
        print(f"\n=== 批次 {start // args.batch + 1}：{len(batch)} 题")
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            records = list(pool.map(lambda inst: run_agent(inst, llm, cfg, run_dir, model_name), batch))
        for rec in records:
            print(f"  agent {rec['instance_id']}: {rec.get('exit_reason')} steps={rec.get('steps', '-')} ${rec.get('cost', 0):.4f}")
        to_eval = [r["instance_id"] for r in records if r.get("patch_lines")]
        resolved = evaluate_batch(to_eval, run_dir, args.run_id, args.eval_workers) if to_eval else set()
        with (run_dir / "results.jsonl").open("a", encoding="utf-8") as f:
            for rec in records:
                rec["resolved"] = rec["instance_id"] in resolved
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print(f"  {'✅' if rec['resolved'] else '❌'} {rec['instance_id']}")
        if not args.keep_images:
            for inst in batch:
                docker("rmi", inst["image"], timeout=300)
        # 额度用完（403）不会被重试，后面每题都会在第一步失败、白拉镜像：直接停，充值后用 --retry-errors 续跑
        if any("HTTP 403" in (r.get("error") or "") for r in records):
            print("\n⛔ 中转站返回 403（额度不足 / 无权限），停止。处理后用 --retry-errors 续跑")
            break

    print("\n" + summarize(load_results(run_dir), 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
