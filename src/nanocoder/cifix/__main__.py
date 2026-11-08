"""命令行入口。需要能用 docker 的环境（本项目用 WSL2）。

    nanocoder fix-ci --repo path/to/repo
    nanocoder fix-ci --repo path/to/repo --log ci.log --out runs/cifix/demo
    nanocoder action        # GitHub Action 用，从环境变量读取事件

fix-ci 只修已提交的代码，不推送也不开 PR。产物：report.md、result.json、messages.json、trace.jsonl；
修复通过时写 fix.patch，被拒绝时写 rejected.patch。退出码：0 已修复，1 其他情况。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from miniagent.config import ConfigError, Settings, load_settings
from miniagent.console import setup_console
from miniagent.trace import Tracer

from .. import CODINGAGENT_ROOT
from ..agent import AgentConfig, AgentResult, CodingAgent
from ..prompts import CI_PROMPT_VERSION, CI_TASK_TEMPLATE
from ..responses_llm import ResponsesLLM
from ..sandbox import Sandbox
from .action import main_from_env
from .config import CIConfig, CIConfigError, load_config
from .env import DockerEnv
from .report import render_report
from .runner import AgentRunner, Outcome, fingerprint_payload, fix_ci

# 同 SWE-bench：长任务中途遇到中转站 429 不要轻易放弃
LLM_RETRY = {"max_retries": 8, "retry_backoff": 2.0}


def build_agent(settings: Settings, config: CIConfig, effort: str, trace_path: Path) -> AgentRunner:
    llm = ResponsesLLM(settings, reasoning_effort=effort, **LLM_RETRY)
    tracer = Tracer(log_dir=trace_path.parent, echo=False, max_summary_chars=20_000)
    tracer.path = trace_path
    limits = config.limits
    agent_config = AgentConfig(
        max_steps=limits.max_steps,
        wall_timeout=limits.wall_timeout,
        cost_limit=float("inf"),  # 单价不可靠，用 token 上限
        max_input_tokens=limits.max_input_tokens,
        prompt=CI_PROMPT_VERSION,
        task_template=CI_TASK_TEMPLATE,
    )
    agent = CodingAgent(llm, agent_config, tracer)

    def run(task: str, sandbox: Sandbox) -> AgentResult:
        return agent.run(task, sandbox)

    return run


def fingerprint(config: CIConfig, model: str, effort: str) -> tuple[str, dict]:
    payload = fingerprint_payload(config, prompt=CI_PROMPT_VERSION, model=model, reasoning=effort)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12], payload


def write_artifacts(out: Path, outcome: Outcome, commit: str, model: str, digest: str, payload: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render_report(outcome, fingerprint=digest, model=model), encoding="utf-8")
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
        "model": model,
        "fingerprint": digest,
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


def fix_command(args: argparse.Namespace, settings: Settings) -> int:
    repo = Path(args.repo).resolve()
    config = load_config(args.config or repo / ".nanocoder.yml")
    ci_log = Path(args.log).read_text(encoding="utf-8", errors="replace") if args.log else None
    out = Path(args.out) if args.out else CODINGAGENT_ROOT / "runs" / "cifix" / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    print(f"修复 {repo} @ {commit[:10]}，镜像 {config.image}，模型 {settings.model}")
    agent = build_agent(settings, config, args.reasoning_effort, out / "trace.jsonl")
    outcome = fix_ci(DockerEnv(repo, config), config, agent, ci_log)
    digest, payload = fingerprint(config, settings.model, args.reasoning_effort)
    write_artifacts(out, outcome, commit, settings.model, digest, payload)
    print(f"结果：{outcome.status}。{outcome.detail}")
    print(f"产物：{out}")
    return 0 if outcome.fixed else 1


def action_command(args: argparse.Namespace, settings: Settings) -> int:
    def run_fix(repo: Path, config: CIConfig, log: str | None) -> tuple[Outcome, str]:
        with tempfile.TemporaryDirectory(prefix="nanocoder-trace-") as tmp:
            agent = build_agent(settings, config, args.reasoning_effort, Path(tmp) / "trace.jsonl")
            return fix_ci(DockerEnv(repo, config), config, agent, log), settings.model

    return main_from_env(dict(os.environ), run_fix)


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
    p = commands.add_parser("action", help="GitHub Action 入口")
    p.add_argument("--reasoning-effort", default="high", choices=["low", "medium", "high"])
    args = parser.parse_args()

    try:
        settings = load_settings()
        return fix_command(args, settings) if args.command == "fix-ci" else action_command(args, settings)
    except (CIConfigError, ConfigError) as e:
        print(f"❌ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
