"""终端输出小工具。"""

from __future__ import annotations

import sys


def setup_console() -> None:
    """避免在 GBK 终端/管道中打印 emoji 时抛出 UnicodeEncodeError：无法编码的字符替换为 ?。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
