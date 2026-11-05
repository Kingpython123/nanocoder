"""读取并校验 .nanocoder.yml。MVP 不猜环境，镜像、依赖安装和检查命令都由用户写明。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# 这些文件一改就可能让检查“变绿”却没有修任何东西（删测试、加 deselect、放宽 lint），默认不许碰。
# 依赖清单也在内：agent 断网，改了依赖也验证不了。需要时用 protected_paths 覆盖。
DEFAULT_PROTECTED = (
    "tests/**", "test/**", "**/tests/**", "**/test/**", "**/test_*.py", "**/*_test.py", "**/conftest.py",
    "pyproject.toml", "setup.cfg", "tox.ini", "pytest.ini", "noxfile.py", "mypy.ini",
    ".flake8", "ruff.toml", ".ruff.toml", ".pre-commit-config.yaml",
)  # fmt: skip
# 用户也不能放开：改了它们，判定标准本身就变了
ALWAYS_PROTECTED = (".nanocoder.yml", ".github/**")


class CIConfigError(Exception):
    """配置文件有问题，错误信息直接给用户看。"""


@dataclass(frozen=True)
class Check:
    name: str
    command: str


@dataclass(frozen=True)
class Limits:
    max_input_tokens: int = 600_000  # 累计输入 token（含缓存命中）
    max_steps: int = 40
    wall_timeout: int = 1800  # 秒，agent 整体
    check_timeout: int = 600  # 秒，每条检查
    setup_timeout: int = 900  # 秒，每条 setup 命令
    memory: str = "4g"
    cpus: float = 2.0


@dataclass(frozen=True)
class CIConfig:
    image: str
    checks: tuple[Check, ...]
    setup: tuple[str, ...] = ()
    protected_paths: tuple[str, ...] = DEFAULT_PROTECTED
    limits: Limits = field(default_factory=Limits)


_TOP_KEYS = {"image", "setup", "checks", "protected_paths", "limits"}


def load_config(path: str | Path) -> CIConfig:
    path = Path(path)
    if not path.is_file():
        raise CIConfigError(f"找不到配置文件：{path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise CIConfigError(f"{path} 不是合法的 YAML：{e}") from e
    return parse_config(data)


def parse_config(data: Any) -> CIConfig:
    if not isinstance(data, dict):
        raise CIConfigError("配置文件的顶层必须是一个映射")
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise CIConfigError(f"未知的配置项：{', '.join(sorted(unknown))}")
    image = data.get("image")
    if not isinstance(image, str) or not image.strip():
        raise CIConfigError("缺少 image（例如 python:3.12）")
    protected = data.get("protected_paths", DEFAULT_PROTECTED)
    return CIConfig(
        image=image.strip(),
        checks=_parse_checks(data.get("checks")),
        setup=tuple(_str_list(data.get("setup", []), "setup")),
        protected_paths=tuple(_str_list(protected, "protected_paths")),
        limits=_parse_limits(data.get("limits", {})),
    )


def _parse_checks(raw: Any) -> tuple[Check, ...]:
    if not isinstance(raw, list) or not raw:
        raise CIConfigError("checks 至少要有一条，每条包含 name 和 command")
    checks = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"name", "command"}:
            raise CIConfigError(f"checks 的每一条必须且只能有 name 和 command：{item!r}")
        if not all(isinstance(item[k], str) and item[k].strip() for k in ("name", "command")):
            raise CIConfigError(f"name 和 command 必须是非空字符串：{item!r}")
        checks.append(Check(item["name"].strip(), item["command"].strip()))
    names = [c.name for c in checks]
    if len(set(names)) != len(names):
        raise CIConfigError(f"checks 里有重复的 name：{', '.join(names)}")
    return tuple(checks)


def _str_list(raw: Any, key: str) -> list[str]:
    if not isinstance(raw, (list, tuple)) or not all(isinstance(x, str) and x.strip() for x in raw):
        raise CIConfigError(f"{key} 必须是非空字符串的列表")
    return [x.strip() for x in raw]


def _parse_limits(raw: Any) -> Limits:
    if not isinstance(raw, dict):
        raise CIConfigError("limits 必须是一个映射")
    defaults = Limits()
    unknown = set(raw) - set(defaults.__dataclass_fields__)
    if unknown:
        raise CIConfigError(f"未知的 limits 项：{', '.join(sorted(unknown))}")
    for key, value in raw.items():
        expected = type(getattr(defaults, key))
        ok = isinstance(value, (int, float)) if expected is float else isinstance(value, expected)
        if not ok or isinstance(value, bool) or (expected is not str and value <= 0):
            raise CIConfigError(f"limits.{key} 的值不合法：{value!r}")
    return Limits(**raw)
