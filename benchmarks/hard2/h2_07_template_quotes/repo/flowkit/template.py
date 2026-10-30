"""Minimal string templates: "Hello {{ user.name | default('there') | upper }}"."""

from __future__ import annotations

import ast
import re
from typing import Any, Callable, Mapping

_EXPR = re.compile(r"\{\{\s*(.*?)\s*\}\}")
_FILTER = re.compile(r"(\w+)\s*(?:\((.*)\))?", re.DOTALL)


class TemplateError(ValueError):
    pass


def _text(fn: Callable[[str], str]) -> Callable[[Any], Any]:
    return lambda value: None if value is None else fn(str(value))


def _default(value: Any, fallback: Any) -> Any:
    return fallback if value in (None, "") else value


def _truncate(value: Any, n: int) -> Any:
    if value is None:
        return None
    s = str(value)
    return s if len(s) <= n else s[:n] + "..."


FILTERS: dict[str, Callable[..., Any]] = {
    "upper": _text(str.upper),
    "lower": _text(str.lower),
    "trim": _text(str.strip),
    "default": _default,
    "truncate": _truncate,
}


def _lookup(context: Mapping[str, Any], path: str) -> Any:
    value: Any = context
    for part in path.split("."):
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        else:
            return None
    return value


def _parse_filter(text: str) -> tuple[str, list[Any]]:
    m = _FILTER.fullmatch(text.strip())
    if not m:
        raise TemplateError(f"bad filter syntax: {text!r}")
    name, raw_args = m.group(1), m.group(2)
    if name not in FILTERS:
        raise TemplateError(f"unknown filter {name!r}")
    if not raw_args:
        return name, []
    try:
        args = ast.literal_eval(f"({raw_args},)")
    except (ValueError, SyntaxError):
        raise TemplateError(f"bad filter arguments: {text!r}") from None
    return name, list(args)


def render(template: str, context: Mapping[str, Any]) -> str:
    """Filters are applied left to right. Filter arguments are Python literals; quoted
    strings may contain '|' and '}}'."""

    def substitute(m: re.Match) -> str:
        path, *filters = (part.strip() for part in m.group(1).split("|"))
        value = _lookup(context, path)
        for f in filters:
            name, args = _parse_filter(f)
            value = FILTERS[name](value, *args)
        return "" if value is None else str(value)

    return _EXPR.sub(substitute, template)
