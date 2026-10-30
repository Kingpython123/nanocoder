"""Pipeline configuration."""

from __future__ import annotations

from typing import Any, Mapping

DEFAULTS: dict[str, Any] = {
    "name": "pipeline",
    "retry": {"max_retries": 3, "base_delay": 0.1, "max_delay": 2.0},
    "logging": {"level": "INFO", "handlers": {"console": {"enabled": True, "format": "%(message)s"}}},
}


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Merge `override` into `base`; nested dicts are merged key by key."""
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key].update(value)
        else:
            result[key] = value
    return result


def load_config(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """DEFAULTS merged with `overrides`. Unknown top-level keys are rejected."""
    overrides = overrides or {}
    unknown = sorted(set(overrides) - set(DEFAULTS))
    if unknown:
        raise KeyError(f"unknown config key(s): {', '.join(unknown)}")
    return deep_merge(DEFAULTS, overrides)
