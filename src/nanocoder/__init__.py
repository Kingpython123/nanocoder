"""nanocoder：P2 Nano Coding Agent（仓库级自动修 bug）。

见 pri/Codingagent/doc/P2-coding-agent.md。
"""

from pathlib import Path

# 项目目录 pri/Codingagent：任务集 benchmarks/ 和实验产物 runs/ 都在这里
CODINGAGENT_ROOT = Path(__file__).resolve().parents[2]

from .agent import AgentConfig, AgentResult, CodingAgent
from .sandbox import LocalSandbox, Sandbox

__all__ = ["CODINGAGENT_ROOT", "AgentConfig", "AgentResult", "CodingAgent", "LocalSandbox", "Sandbox"]
