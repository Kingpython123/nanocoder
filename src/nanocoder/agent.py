"""CodingAgent：在沙箱里修 bug 的 agent loop。

和 miniagent.Agent 的区别：
- 结束条件不是"模型不再调用工具"，而是调用 submit（并通过提交守卫）
- 三重上限：步数、成本、墙钟时间；超限时仍然返回，由调用方照常取当前 diff
- 模型只回文字不调工具时提醒它，连续 3 次就放弃
- 统计 token、成本、工具错误数，供评测报告使用
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from miniagent.llm import LLM, LLMError
from miniagent.trace import Tracer, timed

from .prompts import INSTANCE_TEMPLATE, NO_ACTION_NUDGE, PROMPT_VERSION, SYSTEM_PROMPTS
from .sandbox import Sandbox
from .tools import AgentState, build_registry


@dataclass
class AgentConfig:
    max_steps: int = 40
    cost_limit: float = 0.50  # 美元，单题上限
    wall_timeout: float = 900  # 秒
    max_no_action: int = 3
    # 每百万 token 的价格（美元）。gpt-6-luna 的价格来自第三方，未经核实；中转站价格以账单为准
    price_input: float = 0.10
    price_output: float = 0.50
    prompt: str = PROMPT_VERSION  # 系统提示词版本，见 prompts.SYSTEM_PROMPTS
    max_input_tokens: int | None = None  # 累计输入 token 上限，不依赖单价
    task_template: str = INSTANCE_TEMPLATE  # 含 {issue}


@dataclass
class AgentResult:
    exit_reason: str  # submitted / max_steps / cost_limit / token_limit / wall_timeout / no_action / llm_error
    steps: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0  # 只有 Responses API（E7）会返回；已包含在 completion_tokens 里
    cost: float = 0.0
    wall_time: float = 0.0
    tool_calls: int = 0
    tool_errors: int = 0
    unverified_submit: bool = False
    error: str | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)


class CodingAgent:
    def __init__(self, llm: LLM, config: AgentConfig | None = None, tracer: Tracer | None = None):
        self.llm = llm
        self.config = config or AgentConfig()
        self.tracer = tracer or Tracer()

    def run(self, issue: str, sandbox: Sandbox) -> AgentResult:
        cfg = self.config
        state = AgentState()
        registry = build_registry(sandbox, state)
        tools = registry.schemas()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPTS[self.config.prompt]},
            {"role": "user", "content": cfg.task_template.format(issue=issue)},
        ]
        result = AgentResult(exit_reason="max_steps", messages=messages)
        self.tracer.log(0, "start", {"prompt_version": self.config.prompt, "model": self.llm.model})
        started = time.monotonic()
        no_action = 0

        for step in range(1, cfg.max_steps + 1):
            state.step = step
            result.steps = step
            if time.monotonic() - started > cfg.wall_timeout:
                result.exit_reason = "wall_timeout"
                break
            if result.cost > cfg.cost_limit:
                result.exit_reason = "cost_limit"
                break
            if cfg.max_input_tokens is not None and result.prompt_tokens > cfg.max_input_tokens:
                result.exit_reason = "token_limit"
                break

            try:
                with timed() as t:
                    message = self.llm.chat(messages, tools=tools)
            except LLMError as e:
                result.exit_reason, result.error = "llm_error", str(e)
                self.tracer.log(step, "error", str(e))
                break
            self._account(result, self.llm.last_usage)
            tool_calls = message.tool_calls or []
            self.tracer.log(
                step,
                "llm_call",
                {"content": message.content, "tool_calls": [tc.function.name for tc in tool_calls]},
                duration=t.elapsed,
                cost=round(result.cost, 5),
            )

            if not tool_calls:
                messages.append({"role": "assistant", "content": message.content or ""})
                no_action += 1
                if no_action >= cfg.max_no_action:
                    result.exit_reason = "no_action"
                    break
                messages.append({"role": "user", "content": NO_ACTION_NUDGE})
                continue
            no_action = 0

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [tc.model_dump(exclude_none=True) for tc in tool_calls],
                }
            )
            # 按顺序执行，不并行：两个 edit 同时改一个文件会互相覆盖
            for tc in tool_calls:
                name, arguments = tc.function.name, tc.function.arguments
                self.tracer.log(step, "tool_call", f"{name}({arguments})", tool_call_id=tc.id)
                with timed() as t:
                    output = registry.execute(name, arguments)
                result.tool_calls += 1
                if output.startswith(("Error:", "错误：")):
                    result.tool_errors += 1
                self.tracer.log(step, "tool_result", output, duration=t.elapsed, tool_call_id=tc.id)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})

            if state.submitted:
                result.exit_reason = "submitted"
                break

        result.unverified_submit = state.unverified_submit
        result.wall_time = time.monotonic() - started
        self.tracer.log(result.steps, "final", result.exit_reason, cost=round(result.cost, 5))
        return result

    def _account(self, result: AgentResult, usage: Any) -> None:
        if usage is None:
            return
        prompt = getattr(usage, "prompt_tokens", 0) or 0
        completion = getattr(usage, "completion_tokens", 0) or 0
        details = getattr(usage, "prompt_tokens_details", None)
        cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
        result.prompt_tokens += prompt
        result.completion_tokens += completion
        result.cached_tokens += cached
        result.reasoning_tokens += getattr(usage, "reasoning_tokens", 0) or 0
        result.cost += (prompt * self.config.price_input + completion * self.config.price_output) / 1e6
