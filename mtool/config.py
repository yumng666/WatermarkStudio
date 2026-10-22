"""配置持久化：记住水印文件、输出目录、上次参数。"""
from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "MediaWatermarkTool"

DEFAULTS: dict = {
    "output_dir_video": "",
    "output_dir_image": "",
    "output_dir_gif": "",
    "watermark_image": "",
    "wm_type": "text",          # text | image
    "text": "© 我的水印",
    "position": "br",           # tl tc tr cl c cr bl bc br
    "scale_pct": 12,            # 图片水印宽度 = 画面短边 * pct%
    "opacity": 80,              # 0-100
    "margin_pct": 3,            # 边距 = 短边 * pct%
    "font_pct": 4,              # 文字水印字号 = 画面高 * pct%
    "color": "#FFFFFF",
    "gif_percent": 80,          # 100/90/80/70/60
    "last_input_dir": "",
    "open_after": True,
}


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for k, v in data.items():
                if k in DEFAULTS or k.startswith("ui_"):
                    cfg[k] = v
            # 旧版本只有一个 output_dir，迁移到三个模式各一份
            legacy = data.get("output_dir")
            if legacy and not any(cfg.get(k) for k in
                                  ("output_dir_video", "output_dir_image", "output_dir_gif")):
                for k in ("output_dir_video", "output_dir_image", "output_dir_gif"):
                    cfg[k] = legacy
    except Exception:
        pass
    return cfg


def save(cfg: dict) -> None:
    try:
        d = config_dir()
        d.mkdir(parents=True, exist_ok=True)
        config_path().write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
