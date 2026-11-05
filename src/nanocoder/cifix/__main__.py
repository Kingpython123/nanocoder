"""本地 CLI。需要能用 docker 的环境（本项目用 WSL2）。

    nanocoder fix-ci --repo path/to/repo
    nanocoder fix-ci --repo path/to/repo --log ci.log --out runs/cifix/demo

只修已提交的代码，不推送也不开 PR。产物：report.md、result.json、messages.json、trace.jsonl；
修复通过时写 fix.patch，被拒绝时写 rejected.patch。退出码：0 已修复，1 其他情况。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from miniagent.config import ConfigError, load_settings
from miniagent.console import setup_console
from miniagent.trace import Tracer

from .. import CODINGAGENT_ROOT
from ..agent import AgentConfig, CodingAgent
from ..prompts import CI_PROMPT_VERSION, CI_TASK_TEMPLATE
from ..responses_llm import ResponsesLLM
from .config import CIConfigError, load_config
from .env import DockerEnv
from .report import render_report
from .runner import fingerprint_payload, fix_ci

# 同 SWE-bench：长任务中途遇到中转站 429 不要轻易放弃
LLM_RETRY = {"max_retries": 8, "retry_backoff": 2.0}


def main() -> int:
    setup_console()
    parser = argparse.ArgumentParser(prog="nanocoder")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("fix-ci", help="复现并修复失败的 CI 检查")
    p.add_argument("--repo", default=".", help="本地 git 仓库；只使用已提交的内容")
    p.add_argument("--config", help="默认是仓库里的 .nanocoder.yml")
    p.add_argument("--log", help="CI 失败日志（可选，作为参考）")
    p.add_argument("--out", help="产物目录，默认 runs/cifix/<时间>")
    p.add_argument("--reasoning-effort", default="high", choices=["low", "medium", "high"])
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    try:
        config = load_config(args.config or repo / ".nanocoder.yml")
        settings = load_settings()
    except (CIConfigError, ConfigError) as e:
        print(f"❌ {e}")
        return 1
    ci_log = Path(args.log).read_text(encoding="utf-8", errors="replace") if args.log else None
    out = Path(args.out) if args.out else CODINGAGENT_ROOT / "runs" / "cifix" / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)

    llm = ResponsesLLM(settings, reasoning_effort=args.reasoning_effort, **LLM_RETRY)
    tracer = Tracer(log_dir=out, echo=False, max_summary_chars=20_000)
    tracer.path = out / "trace.jsonl"
    limits = config.limits
    agent_config = AgentConfig(
        max_steps=limits.max_steps,
        wall_timeout=limits.wall_timeout,
        cost_limit=float("inf"),  # 单价不可靠，用 token 上限
        max_input_tokens=limits.max_input_tokens,
        prompt=CI_PROMPT_VERSION,
        task_template=CI_TASK_TEMPLATE,
    )

    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    payload = fingerprint_payload(config, prompt=CI_PROMPT_VERSION, model=settings.model, reasoning=args.reasoning_effort)
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]

    print(f"修复 {repo} @ {commit[:10]}，镜像 {config.image}，模型 {settings.model}")
    outcome = fix_ci(DockerEnv(repo, config), config, CodingAgent(llm, agent_config, tracer).run, ci_log)

    report = render_report(outcome, fingerprint=fingerprint, model=settings.model)
    (out / "report.md").write_text(report, encoding="utf-8")
    if outcome.patch:
        name = "fix.patch" if outcome.fixed else "rejected.patch"
        (out / name).write_text(outcome.patch, encoding="utf-8", newline="")
    agent = outcome.agent
    if agent:
        (out / "messages.json").write_text(json.dumps(agent.messages, ensure_ascii=False, indent=1), encoding="utf-8")
    result = {
        "status": outcome.status,
        "detail": outcome.detail,
        "commit": commit,
        "model": settings.model,
        "fingerprint": fingerprint,
        "config": payload,
        "changed_files": outcome.changed_files,
        "before": {r.name: r.exit_code for r in outcome.before},
        "after": {r.name: r.exit_code for r in outcome.after},
    }
    if agent:
        result.update(
            exit_reason=agent.exit_reason,
            steps=agent.steps,
            prompt_tokens=agent.prompt_tokens,
            cached_tokens=agent.cached_tokens,
            completion_tokens=agent.completion_tokens,
            wall_time=round(agent.wall_time, 1),
        )
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"结果：{outcome.status}。{outcome.detail}")
    print(f"产物：{out}")
    return 0 if outcome.fixed else 1


if __name__ == "__main__":
    sys.exit(main())
