"""视频批量转 GIF：保持原帧率与长宽比，按分辨率百分比缩放。"""
from __future__ import annotations

from pathlib import Path

from .ffmpeg_tools import MediaInfo

PERCENTS = (100, 90, 80, 70, 60)
MAX_FPS = 50.0  # GIF 的帧延迟单位为 1/100s，超过 50fps 没有意义


def gif_size(info: MediaInfo, percent: int) -> tuple[int, int]:
    w = max(2, round(info.width * percent / 100))
    h = max(2, round(info.height * w / info.width)) if info.width else info.height
    return w, h


def build_gif_args(info: MediaInfo, percent: int, out_path: str) -> list[str]:
    w, _ = gif_size(info, percent)
    fps = min(info.fps if info.fps > 0 else 25.0, MAX_FPS)
    fc = (
        f"[0:v]fps={fps:.3f},scale={w}:-1:flags=lanczos,split[a][b];"
        f"[a]palettegen=max_colors=256:stats_mode=diff[p];"
        f"[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    return ["-i", info.path, "-filter_complex", fc, "-loop", "0", out_path]


def gif_output_path(src: str, out_dir: str) -> str:
    return str(Path(out_dir) / f"{Path(src).stem}.gif")
