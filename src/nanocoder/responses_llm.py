"""E7：用 Responses API 调模型，这样可以"开着推理用工具"。

gpt-6-luna 在 /v1/chat/completions 下只要开推理就拒绝工具调用，/v1/responses 没有这个限制。
这个类对外和 miniagent.llm.LLM 一样（chat() 返回 ChatCompletionMessage，last_usage 有
prompt_tokens / completion_tokens），agent loop 一行不用改。

每次调用都把 chat 格式的 messages 转成 Responses 的 input（store=False，不依赖服务端状态）。
推理内容（reasoning item，加密）要原样传回，模型下一步才接得上自己的思路：这里按"它后面紧跟的
第一个 function_call 的 call_id"记下来，重建 input 时插回原位。
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any

from openai import OpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageFunctionToolCall

from miniagent.config import Settings
from miniagent.llm import _RETRYABLE, LLMError, _describe


class ResponsesLLM:
    def __init__(self, settings: Settings, reasoning_effort: str = "medium", max_retries: int = 2, retry_backoff: float = 1.0):
        self.model = settings.model
        self.reasoning_effort = reasoning_effort
        self.last_usage: Any = None
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=settings.timeout, max_retries=0)
        self._reasoning: dict[str, list[dict]] = {}  # call_id -> 它前面的 reasoning items
        self._lock = threading.Lock()  # 多个 worker 线程共用一个实例

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> ChatCompletionMessage:
        instructions, items = self._to_input(messages)
        params: dict[str, Any] = {
            "model": self.model,
            "input": items,
            "store": False,
            "reasoning": {"effort": self.reasoning_effort},
            "include": ["reasoning.encrypted_content"],
        }
        if instructions:
            params["instructions"] = instructions
        if tools:
            params["tools"] = [_to_response_tool(t) for t in tools]

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.responses.create(**params)
                break
            except _RETRYABLE as e:
                if attempt >= self.max_retries:
                    raise LLMError(_describe(e) + f"（已重试 {self.max_retries} 次）") from e
                wait = self.retry_backoff * (2**attempt)
                print(f"⚠️ 请求失败：{_describe(e)}，{wait:.0f} 秒后重试……")
                time.sleep(wait)
            except OpenAIError as e:
                raise LLMError(_describe(e)) from e

        self.last_usage = _to_chat_usage(getattr(response, "usage", None))
        texts, calls, pending_reasoning = [], [], []
        for item in response.output:
            if item.type == "reasoning":
                pending_reasoning.append(item.model_dump(exclude_none=True))
            elif item.type == "function_call":
                if pending_reasoning:
                    with self._lock:
                        self._reasoning[item.call_id] = pending_reasoning
                    pending_reasoning = []
                calls.append(
                    ChatCompletionMessageFunctionToolCall(
                        id=item.call_id, type="function", function={"name": item.name, "arguments": item.arguments}
                    )
                )
            elif item.type == "message":
                texts += [c.text for c in item.content if getattr(c, "type", "") == "output_text"]
        return ChatCompletionMessage(role="assistant", content="\n".join(texts) or None, tool_calls=calls or None)

    def _to_input(self, messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        instructions, items = [], []
        for m in messages:
            role = m["role"]
            if role == "system":
                instructions.append(m["content"])
            elif role == "user":
                items.append({"role": "user", "content": m["content"]})
            elif role == "assistant":
                if m.get("content"):
                    items.append({"role": "assistant", "content": m["content"]})
                for tc in m.get("tool_calls") or []:
                    with self._lock:
                        items += self._reasoning.get(tc["id"], [])
                    fn = tc["function"]
                    items.append({"type": "function_call", "call_id": tc["id"], "name": fn["name"], "arguments": fn["arguments"]})
            elif role == "tool":
                items.append({"type": "function_call_output", "call_id": m["tool_call_id"], "output": m["content"]})
        return "\n\n".join(instructions), items


def _to_response_tool(tool: dict[str, Any]) -> dict[str, Any]:
    fn = tool["function"]
    # Responses API 默认 strict=True，要求所有参数都 required；我们的工具有可选参数，所以关掉
    return {"type": "function", "name": fn["name"], "description": fn.get("description", ""), "parameters": fn["parameters"], "strict": False}


def _to_chat_usage(usage: Any) -> Any:
    """把 Responses 的 usage 换成 chat 的字段名，CodingAgent._account() 照常统计。输出 token 包含推理 token。"""
    if usage is None:
        return None
    in_details = getattr(usage, "input_tokens_details", None)
    out_details = getattr(usage, "output_tokens_details", None)
    return SimpleNamespace(
        prompt_tokens=usage.input_tokens,
        completion_tokens=usage.output_tokens,
        prompt_tokens_details=SimpleNamespace(cached_tokens=getattr(in_details, "cached_tokens", 0) or 0),
        reasoning_tokens=getattr(out_details, "reasoning_tokens", 0) or 0,
    )
