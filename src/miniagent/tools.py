"""工具系统：@tool 装饰器 + ToolRegistry。

用法：

    from typing import Annotated
    from pydantic import Field

    @tool
    def add(a: int, b: Annotated[int, Field(description="第二个加数")] = 0) -> int:
        \"\"\"两个整数相加。\"\"\"
        return a + b

    registry = ToolRegistry()
    registry.register(add)
    registry.schemas()                      # 传给 llm.chat(tools=...)
    registry.execute("add", '{"a": 1, "b": 2}')   # -> "3"

原理：函数签名 + 类型注解 -> Pydantic 模型 -> JSON Schema -> OpenAI 工具格式。
模型返回的 arguments（JSON 字符串）再用同一个 Pydantic 模型校验，保证类型正确。
"""

from __future__ import annotations

import inspect
import json
import typing
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError, create_model


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., Any]
    args_model: type[BaseModel]

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # 被 @tool 装饰后仍可当普通函数直接调用
        return self.func(*args, **kwargs)

    def schema(self) -> dict[str, Any]:
        """导出 OpenAI function calling 格式的工具定义。"""
        params = self.args_model.model_json_schema()
        _strip_titles(params)
        params.setdefault("properties", {})
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": params,
            },
        }


def tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Any:
    """把普通函数变成 Tool。支持 @tool 和 @tool(name=..., description=...) 两种写法。

    - name 默认取函数名
    - description 默认取 docstring（模型靠它判断何时调用这个工具，要写清楚）
    - 每个参数都必须有类型注解；参数说明可用 Annotated[类型, Field(description=...)]
    """

    def decorator(f: Callable[..., Any]) -> Tool:
        tool_name = name or f.__name__
        doc = description or inspect.getdoc(f) or ""
        if not doc:
            raise ValueError(f"工具 {tool_name} 缺少描述：请写 docstring 或传入 description")
        return Tool(
            name=tool_name,
            description=doc,
            func=f,
            args_model=_build_args_model(f, tool_name),
        )

    return decorator(func) if func is not None else decorator


def _build_args_model(f: Callable[..., Any], tool_name: str) -> type[BaseModel]:
    """根据函数签名动态生成 Pydantic 模型。"""
    hints = typing.get_type_hints(f, include_extras=True)  # 解析字符串注解，保留 Annotated
    fields: dict[str, Any] = {}
    for p in inspect.signature(f).parameters.values():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            raise TypeError(f"工具 {tool_name} 不支持 *args / **kwargs 参数")
        if p.name not in hints:
            raise TypeError(f"工具 {tool_name} 的参数 {p.name} 缺少类型注解")
        default = ... if p.default is inspect.Parameter.empty else p.default
        fields[p.name] = (hints[p.name], default)
    return create_model(f"{tool_name}_args", **fields)


def _strip_titles(schema: Any) -> None:
    """去掉 Pydantic 自动生成的 title 字段，让 schema 更干净（模型不需要它）。"""
    if isinstance(schema, dict):
        schema.pop("title", None)
        for key, value in schema.items():
            if key == "properties" and isinstance(value, dict):
                for prop in value.values():
                    _strip_titles(prop)
            else:
                _strip_titles(value)
    elif isinstance(schema, list):
        for item in schema:
            _strip_titles(item)


class ToolRegistry:
    """工具注册中心：统一管理工具 schema 和执行。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, t: Tool | Callable[..., Any]) -> Tool:
        """注册工具；传入普通函数时会自动用 @tool 包装。"""
        if not isinstance(t, Tool):
            t = tool(t)
        if t.name in self._tools:
            raise ValueError(f"工具名重复：{t.name}")
        self._tools[t.name] = t
        return t

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        """全部工具的 schema 列表，直接传给 llm.chat(tools=...)。"""
        return [t.schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: str | dict[str, Any] | None) -> str:
        """执行工具并返回字符串结果。

        任何错误都不抛异常，而是返回以“错误：”开头的说明文字。
        这些文字会作为 tool 消息发回给模型，模型看到后通常能自我纠正。
        """
        t = self._tools.get(name)
        if t is None:
            return f"错误：未知工具 {name!r}。可用工具：{', '.join(self._tools) or '（无）'}"

        # 1. 解析 JSON（模型给的 arguments 是字符串）
        if isinstance(arguments, dict):
            args = arguments
        else:
            text = (arguments or "").strip() or "{}"
            try:
                args = json.loads(text)
            except json.JSONDecodeError as e:
                return f"错误：工具 {name!r} 的参数不是合法 JSON（{e.msg}，位置 {e.pos}）。收到：{text[:200]}"
        if not isinstance(args, dict):
            return f"错误：工具 {name!r} 的参数必须是 JSON 对象，收到的是 {type(args).__name__}"

        # 2. 用 Pydantic 校验参数类型
        try:
            validated = t.args_model.model_validate(args)
        except ValidationError as e:
            details = "\n".join(
                f"- {'.'.join(map(str, err['loc'])) or '(根)'}：{err['msg']}（收到 {err.get('input')!r}）"
                for err in e.errors(include_url=False)
            )
            return f"错误：工具 {name!r} 参数校验失败：\n{details}"

        # 3. 调用函数（用属性而不是 model_dump，保留嵌套模型等对象类型）
        kwargs = {field: getattr(validated, field) for field in type(validated).model_fields}
        try:
            result = t.func(**kwargs)
        except Exception as e:
            return f"错误：工具 {name!r} 执行失败：{type(e).__name__}: {e}"

        return _to_text(result)


def _to_text(result: Any) -> str:
    """把工具返回值统一转成字符串。"""
    if isinstance(result, str):
        return result
    if result is None:
        return "（工具执行成功，无返回值）"
    if isinstance(result, BaseModel):
        return result.model_dump_json()
    if isinstance(result, (dict, list, tuple)):
        return json.dumps(result, ensure_ascii=False, default=str)
    return str(result)
