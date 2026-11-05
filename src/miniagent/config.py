"""配置读取：从项目根目录的 .env 文件加载中转站配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录：src/miniagent/config.py 往上两级
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class ConfigError(Exception):
    """配置缺失或格式错误。错误信息直接展示给用户，所以要写清楚怎么修。"""


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    max_steps: int = 10
    timeout: float = 60.0  # 单次请求超时（秒）
    # 可选：推理强度（none / low / medium / high）。为空则不发送该参数。
    # 部分推理模型在 /v1/chat/completions 下开着推理时不支持工具调用，需要设为 none。
    reasoning_effort: str | None = None

    def masked_key(self) -> str:
        """打印用的脱敏 key，例如 sk-a****wxyz。"""
        k = self.api_key
        return k[:4] + "****" + k[-4:] if len(k) > 8 else "****"


def load_settings(env_file: str | Path | None = None) -> Settings:
    """读取 .env 并返回 Settings；缺少必填项时抛出 ConfigError。

    .env 中的值会覆盖系统环境变量，避免系统里残留的 OPENAI_API_KEY
    （比如官方 key）和中转站配置混用。
    """
    path = Path(env_file) if env_file else DEFAULT_ENV_FILE
    if path.exists():
        # utf-8-sig：兼容记事本等编辑器保存的带 BOM 的 UTF-8 文件
        load_dotenv(path, override=True, encoding="utf-8-sig")

    required = {
        "OPENAI_API_KEY": "中转站的 API Key",
        "OPENAI_BASE_URL": "中转站地址，例如 https://your-relay.example.com/v1",
        "MODEL_NAME": "模型名，需支持 function calling",
    }
    values = {name: os.getenv(name, "").strip() for name in required}
    missing = [name for name, v in values.items() if not v]
    if missing:
        lines = [f"  - {name}：{required[name]}" for name in missing]
        if not path.exists():
            hint = (
                f"没有找到配置文件 {path}。\n"
                "请先执行：Copy-Item .env.example .env，然后填写以下配置："
            )
        else:
            hint = f"配置文件 {path} 中缺少以下配置："
        raise ConfigError(hint + "\n" + "\n".join(lines))

    if not values["OPENAI_BASE_URL"].startswith(("http://", "https://")):
        raise ConfigError(
            f"OPENAI_BASE_URL 格式不对：{values['OPENAI_BASE_URL']!r}，"
            "应以 http:// 或 https:// 开头，通常以 /v1 结尾。"
        )

    raw_steps = os.getenv("MAX_STEPS", "10").strip() or "10"
    try:
        max_steps = int(raw_steps)
    except ValueError:
        raise ConfigError(f"MAX_STEPS 必须是整数，当前为 {raw_steps!r}") from None
    if max_steps < 1:
        raise ConfigError(f"MAX_STEPS 必须 >= 1，当前为 {max_steps}")

    return Settings(
        api_key=values["OPENAI_API_KEY"],
        base_url=values["OPENAI_BASE_URL"].rstrip("/"),
        model=values["MODEL_NAME"],
        max_steps=max_steps,
        reasoning_effort=os.getenv("REASONING_EFFORT", "").strip() or None,
    )
