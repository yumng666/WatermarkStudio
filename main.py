"""水印工坊 · 批量水印与 GIF 转换 启动入口。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mtool.ui import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
