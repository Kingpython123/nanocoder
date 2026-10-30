"""Pipeline configuration."""

from __future__ import annotations

from typing import Any, Mapping

DEFAULTS: dict[str, Any] = {
    "name": "pipeline",
    "retry": {"max_retries": 3, "base_delay": 0.1, "max_delay": 2.0},
    "logging": {"level": "INFO", "handlers": {"console": {"enabled": True, "format": "%(message)s"}}},
}

ENV_PREFIX = "FLOWKIT_"


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Merge `override` into `base`; nested dicts are merged key by key."""
    result: dict[str, Any] = {}
    for key, value in base.items():
        result[key] = deep_merge(value, {}) if isinstance(value, Mapping) else value
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        elif isinstance(value, Mapping):
            result[key] = deep_merge(value, {})
        else:
            result[key] = value
    return result


def env_overrides(environ: Mapping[str, str]) -> dict[str, Any]:
    """Config overrides from environment variables (see README, "Environment variables")."""
    result: dict[str, Any] = {}
    for name, raw in sorted(environ.items()):
        if not name.upper().startswith(ENV_PREFIX):
            continue
        path = name[len(ENV_PREFIX) :].lower().split("_")
        value = raw
        node = result
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = value
    return result


def load_config(overrides: Mapping[str, Any] | None = None, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """DEFAULTS, then environment variables (when `environ` is given), then `overrides`.

    Unknown top-level keys are rejected.
    """
    overrides = overrides or {}
    from_env = env_overrides(environ or {})
    unknown = sorted((set(overrides) | set(from_env)) - set(DEFAULTS))
    if unknown:
        raise KeyError(f"unknown config key(s): {', '.join(unknown)}")
    return deep_merge(deep_merge(DEFAULTS, from_env), overrides)
