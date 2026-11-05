"""第 1 周：最小的 agent loop。

agent 的本质就是一个循环：
    问模型 -> 模型说要调用工具 -> 执行工具 -> 把结果告诉模型 -> 再问模型 -> …… -> 模型给出最终答案

这个文件里用到的现成组件：
- self.llm.chat(messages, tools=...)       返回 message 对象（看 .content 和 .tool_calls）
- self.registry.schemas()                 所有工具的 schema 列表
- self.registry.execute(name, arguments)  执行工具，永远返回字符串（出错也是字符串）
- self.tracer.log(step, type, content, duration=..., **extra)   记录一步
- miniagent.trace.timed()                 计时用的上下文管理器

运行：python main.py
"""

from __future__ import annotations

from typing import Any

from .llm import LLM
from .tools import ToolRegistry
from .trace import Tracer, timed

DEFAULT_SYSTEM_PROMPT = (
    "你是一个乐于助人的助手。需要精确计算、查询时间或读取文件时，请调用提供的工具，"
    "不要自己猜测结果。拿到工具结果后，用中文简洁地回答用户。"
)


class Agent:
    def __init__(
        self,
        llm: LLM,
        registry: ToolRegistry,
        max_steps: int = 10,
        tracer: Tracer | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ):
        self.llm = llm
        self.registry = registry
        self.max_steps = max_steps
        self.tracer = tracer or Tracer()
        self.system_prompt = system_prompt

    def run(self, user_input: str) -> str:
        """执行一次完整的 agent 循环，返回最终答案。"""

        # ── (1) 初始化对话 ────────────────────────────────────────────
        # messages 就是 agent 的全部"记忆"。模型本身是无状态的，
        # 每次调用都要把完整的历史发过去，它才知道之前发生了什么。
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        # 工具清单（JSON Schema）。模型就是靠这里的 name / description / parameters
        # 来决定"要不要调用工具、调用哪个、传什么参数"。
        # 没有注册任何工具时传 None，部分中转站收到空列表会报错。
        tools = self.registry.schemas() or None

        # ── (2) 主循环：最多 max_steps 轮 ─────────────────────────────
        # 必须有上限：模型可能反复调用工具停不下来，没有上限就会无限烧 token。
        for step in range(1, self.max_steps + 1):

            # ── (3) 问模型 ────────────────────────────────────────────
            with timed() as t:
                message = self.llm.chat(messages, tools=tools)

            # 模型的回复只有两种可能：
            #   a. 带 tool_calls：表示"我需要先调用这些工具"
            #   b. 不带 tool_calls：content 就是给用户的最终答案
            tool_calls = message.tool_calls or []

            self.tracer.log(
                step,
                "llm_call",
                {
                    "content": message.content,
                    "tool_calls": [tc.function.name for tc in tool_calls],
                },
                duration=t.elapsed,
            )

            # ── (5) 没有工具调用 -> 这就是最终答案，循环结束 ──────────
            if not tool_calls:
                answer = message.content or ""
                self.tracer.log(step, "final", answer)
                return answer

            # ── (4) 有工具调用 ────────────────────────────────────────
            # (4a) 先把 assistant 这条消息"原样"放回历史。
            # 下一轮的 tool 消息要通过 tool_call_id 指向这里的某个调用，
            # 漏掉这条，接口会返回 400：tool 消息找不到对应的调用。
            # model_dump 把 SDK 的对象转成普通 dict，exclude_none 去掉空字段。
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,  # 有 tool_calls 时通常是 None，正常
                    "tool_calls": [tc.model_dump(exclude_none=True) for tc in tool_calls],
                }
            )

            # (4b) 模型可能一次要求多个调用（比如同时算数 + 查时间），
            # 每一个都要执行，并且各自回一条 tool 消息，少一条也会报错。
            for tc in tool_calls:
                name = tc.function.name
                arguments = tc.function.arguments  # 注意：这是 JSON 字符串，不是 dict

                self.tracer.log(step, "tool_call", f"{name}({arguments})", tool_call_id=tc.id)

                # registry.execute 负责解析 JSON、校验参数、调用函数。
                # 出错时不抛异常，而是返回"错误：……"字符串。
                # 这样模型能看到错误原因，下一轮自己修正参数重试，这就是 agent 的"自我纠错"。
                with timed() as t:
                    result = self.registry.execute(name, arguments)

                self.tracer.log(
                    step, "tool_result", result, duration=t.elapsed, tool_call_id=tc.id
                )

                # (4c) 工具结果以 role=tool 追加，tool_call_id 必须和上面的调用一一对应。
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

            # 到这里本轮结束，回到循环开头：模型会带着工具结果再思考一次。

        # ── (6) 跑满 max_steps 还没得到答案 ──────────────────────────
        answer = (
            f"已达到最大步数 {self.max_steps}，仍未得到最终答案。"
            "可以调大 MAX_STEPS 或换个问法。"
        )
        self.tracer.log(self.max_steps, "final", answer, reason="max_steps")
        return answer
