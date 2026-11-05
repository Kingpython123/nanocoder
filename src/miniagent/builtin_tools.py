"""内置示例工具：calculator、get_current_time、read_file。

想加自己的工具？照着下面的写法：一个带类型注解和 docstring 的函数 + @tool，
然后在 default_registry() 里注册即可。
"""

from __future__ import annotations

import ast
import operator
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import Field

from .config import PROJECT_ROOT
from .tools import ToolRegistry, tool

# ---------------------------------------------------------------- calculator

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_MAX_EXPR_LEN = 200
_MAX_EXPONENT = 100  # 限制幂运算，防止 9**9**9 这类表达式卡死进程


def _safe_eval(node: ast.AST) -> int | float:
    """只允许数字和四则/幂/取模运算的 AST 求值，绝不使用 eval。"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left, right = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError(f"指数过大（最大 {_MAX_EXPONENT}）")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"不支持的表达式元素：{type(node).__name__}（只支持数字和 + - * / // % **）")


@tool
def calculator(
    expression: Annotated[str, Field(description="数学表达式，例如 (123*456)+789")],
) -> str:
    """计算数学表达式，支持 + - * / // % ** 和括号。需要精确计算时请使用此工具。"""
    if len(expression) > _MAX_EXPR_LEN:
        raise ValueError(f"表达式过长（最多 {_MAX_EXPR_LEN} 个字符）")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError:
        raise ValueError(f"表达式语法错误：{expression!r}") from None
    return str(_safe_eval(tree))


# ---------------------------------------------------------- get_current_time

_WEEKDAYS = "一二三四五六日"


@tool
def get_current_time() -> str:
    """获取本机当前的日期、时间和星期。"""
    now = datetime.now().astimezone()
    return f"{now:%Y-%m-%d %H:%M:%S} {now.tzname()} 星期{_WEEKDAYS[now.weekday()]}"


# ----------------------------------------------------------------- read_file

WORKSPACE = PROJECT_ROOT.resolve()
_BLOCKED_NAMES = {".env"}  # 存放密钥的文件不允许读取


@tool
def read_file(
    path: Annotated[str, Field(description="相对于工作区根目录的文件路径，例如 README.md")],
    max_chars: Annotated[int, Field(description="最多返回的字符数", ge=1, le=20000)] = 4000,
) -> str:
    """读取工作区内的文本文件内容。只能读取工作区目录内的文件。"""
    target = (WORKSPACE / path).resolve()  # resolve 会展开 .. 和符号链接
    if not target.is_relative_to(WORKSPACE):
        raise PermissionError(f"拒绝访问：{path!r} 不在工作区 {WORKSPACE} 内")
    if target.name in _BLOCKED_NAMES:
        raise PermissionError(f"拒绝访问：{target.name} 包含密钥，不允许读取")
    if not target.is_file():
        raise FileNotFoundError(f"文件不存在：{path}")
    text = target.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n……（已截断，文件共 {len(text)} 个字符）"
    return text


# ------------------------------------------------------------------ registry


def default_registry() -> ToolRegistry:
    """返回注册了全部内置工具的 ToolRegistry。"""
    registry = ToolRegistry()
    for t in (calculator, get_current_time, read_file):
        registry.register(t)
    return registry
