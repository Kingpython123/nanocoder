"""LLM 封装：对 openai.OpenAI 的一层薄包装，适配 OpenAI 兼容的中转站。"""

from __future__ import annotations

import time
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    InternalServerError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from openai.types.chat import ChatCompletionMessage

from .config import Settings

# 这几类错误通常是暂时性的，值得重试（APITimeoutError 是 APIConnectionError 的子类）
_RETRYABLE = (APIConnectionError, RateLimitError, InternalServerError)


class LLMError(Exception):
    """调用模型失败（已重试过）。错误信息可直接展示给用户。"""


class LLM:
    def __init__(self, settings: Settings, max_retries: int = 2, retry_backoff: float = 1.0):
        self.model = settings.model
        self.reasoning_effort = settings.reasoning_effort
        self.last_usage: Any = None  # 最近一次响应的 usage（token 统计），中转站没返回时为 None
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        # 关闭 SDK 自带的重试，由下面的 chat() 显式重试，方便看清楚发生了什么
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout,
            max_retries=0,
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ChatCompletionMessage:
        """发送一次对话请求，返回原始的 message 对象（choices[0].message）。

        关注两个字段：
        - message.content     模型的文本回复（调用工具时可能为 None）
        - message.tool_calls  模型请求调用的工具列表（没有则为 None）
        """
        params: dict[str, Any] = {"model": self.model, "messages": messages, **kwargs}
        if tools:
            params["tools"] = tools
        # 配置了 REASONING_EFFORT 时才发送；调用方显式传入的值优先
        if self.reasoning_effort and "reasoning_effort" not in params:
            params["reasoning_effort"] = self.reasoning_effort

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**params)
                break
            except _RETRYABLE as e:
                if attempt >= self.max_retries:
                    raise LLMError(_describe(e) + f"（已重试 {self.max_retries} 次）") from e
                wait = self.retry_backoff * (2**attempt)
                print(f"⚠️ 请求失败：{_describe(e)}，{wait:.0f} 秒后重试……")
                time.sleep(wait)
            except OpenAIError as e:  # 4xx 等不可重试的错误
                raise LLMError(_describe(e)) from e

        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMError(f"响应中没有 choices，中转站返回内容可能不兼容：{str(response)[:300]}")
        self.last_usage = getattr(response, "usage", None)
        return choices[0].message


def _describe(e: Exception) -> str:
    """把 openai 的异常转成一句可读的中文描述。"""
    if isinstance(e, APIStatusError):
        hints = {
            401: "API Key 无效，请检查 OPENAI_API_KEY",
            403: "没有权限，请检查 key 的权限或余额",
            404: "接口或模型不存在，请检查 OPENAI_BASE_URL（通常以 /v1 结尾）和 MODEL_NAME",
            429: "请求过于频繁或额度不足",
        }
        hint = hints.get(e.status_code, "服务端返回错误")
        return f"HTTP {e.status_code}，{hint}。详情：{str(e.message)[:300]}"
    if isinstance(e, APIConnectionError):
        return f"无法连接到服务（{type(e).__name__}），请检查网络和 OPENAI_BASE_URL"
    return f"{type(e).__name__}: {e}"
