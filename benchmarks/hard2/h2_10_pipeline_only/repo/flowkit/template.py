"""Minimal string templates: "Hello {{ user.name | default('there') | upper }}"."""

from __future__ import annotations

import ast
import re
from typing import Any, Callable, Iterator, Mapping

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


def _split_pipes(expr: str) -> list[str]:
    """Split on '|' that are not inside a quoted string."""
    parts, buf, quote, i = [], [], None, 0
    while i < len(expr):
        ch = expr[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(expr):
                buf.append(expr[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch == "|":
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if quote:
        raise TemplateError(f"unterminated string in {expr!r}")
    parts.append("".join(buf).strip())
    return parts


def _expressions(template: str) -> Iterator[tuple[int, int, str]]:
    """Yield (start, end, inner text) for each {{ ... }}; '}}' inside quotes does not close it."""
    pos = 0
    while (start := template.find("{{", pos)) != -1:
        i, quote = start + 2, None
        while i < len(template):
            ch = template[i]
            if quote:
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "'\"":
                quote = ch
            elif template.startswith("}}", i):
                break
            i += 1
        else:
            raise TemplateError(f"unclosed '{{{{' at position {start}")
        yield start, i + 2, template[start + 2 : i]
        pos = i + 2


def render(template: str, context: Mapping[str, Any]) -> str:
    """Filters are applied left to right. Filter arguments are Python literals; quoted
    strings may contain '|' and '}}'."""
    out, pos = [], 0
    for start, end, inner in _expressions(template):
        path, *filters = _split_pipes(inner.strip())
        value = _lookup(context, path)
        for f in filters:
            name, args = _parse_filter(f)
            value = FILTERS[name](value, *args)
        out.append(template[pos:start])
        out.append("" if value is None else str(value))
        pos = end
    out.append(template[pos:])
    return "".join(out)
