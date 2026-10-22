"""ffmpeg / ffprobe 定位、媒体探测与带进度的命令执行。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _exe(name: str) -> str:
    return name + ".exe" if os.name == "nt" else name


def _candidate_dirs():
    root = Path(__file__).resolve().parent.parent
    env = os.environ.get("MTOOL_FFMPEG")
    if env:
        p = Path(env)
        yield p if p.is_dir() else p.parent
    for d in (
        root / "ffmpeg" / "bin",
        root / "bin",
        Path(sys.executable).resolve().parent / "ffmpeg" / "bin",
        Path(sys.executable).resolve().parent / "bin",
    ):
        yield d


def find_tools() -> tuple[str | None, str | None]:
    """返回 (ffmpeg, ffprobe) 的绝对路径，找不到则返回 None。"""
    for d in _candidate_dirs():
        f = d / _exe("ffmpeg")
        p = d / _exe("ffprobe")
        if f.exists():
            return str(f), str(p if p.exists() else "")
    f = shutil.which("ffmpeg")
    if f:
        p = shutil.which("ffprobe") or ""
        if not p:
            guess = Path(f).with_name(_exe("ffprobe"))
            p = str(guess) if guess.exists() else ""
        return f, p
    for raw in (
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"D:\FFmpegFreeUI\ffmpeg\bin\ffmpeg.exe",
    ):
        if Path(raw).exists():
            p = str(Path(raw).with_name("ffprobe.exe"))
            return raw, p if Path(p).exists() else ""
    return None, None


def is_bundled(ffmpeg_path: str) -> bool:
    """ffmpeg 是否随程序一起分发（位于 exe 目录或 _MEIPASS 内）。"""
    try:
        target = Path(ffmpeg_path).resolve()
    except Exception:
        return False
    roots = [Path(sys.executable).resolve().parent]
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        roots.append(Path(meipass).resolve())
    for root in roots:
        if root == target.parent or root in target.parents:
            return True
    return False


@dataclass
class MediaInfo:
    path: str
    width: int
    height: int
    duration: float
    fps: float
    fps_raw: str
    pix_fmt: str
    vcodec: str
    has_audio: bool
    acodec: str

    @property
    def short_side(self) -> int:
        return min(self.width, self.height)


def probe(ffprobe: str, path: str) -> MediaInfo:
    cmd = [
        ffprobe, "-v", "error", "-show_streams", "-show_format",
        "-of", "json", path,
    ]
    raw = subprocess.run(
        cmd, capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW
    )
    if raw.returncode != 0:
        raise RuntimeError(raw.stderr.decode("utf-8", "replace").strip() or "ffprobe 失败")
    data = json.loads(raw.stdout.decode("utf-8", "replace") or "{}")
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise RuntimeError("没有视频流")
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)

    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    rotation = 0
    for sd in v.get("side_data_list") or []:
        if "rotation" in sd:
            try:
                rotation = int(float(sd["rotation"]))
            except Exception:
                pass
    if abs(rotation) % 180 == 90:
        w, h = h, w

    fps_raw = v.get("avg_frame_rate") or "0/0"
    try:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except Exception:
        fps = 0.0
    if fps <= 0:
        fps_raw = v.get("r_frame_rate") or "25/1"
        try:
            num, den = fps_raw.split("/")
            fps = float(num) / float(den) if float(den) else 25.0
        except Exception:
            fps = 25.0

    duration = 0.0
    for src in (data.get("format") or {}, v):
        try:
            duration = float(src.get("duration") or 0)
        except Exception:
            duration = 0.0
        if duration > 0:
            break

    return MediaInfo(
        path=path, width=w, height=h, duration=duration, fps=fps or 25.0,
        fps_raw=fps_raw, pix_fmt=v.get("pix_fmt") or "yuv420p",
        vcodec=v.get("codec_name") or "", has_audio=a is not None,
        acodec=(a or {}).get("codec_name") or "",
    )


@dataclass
class RunResult:
    ok: bool
    code: int
    stderr: str
    cancelled: bool = False


def run_ffmpeg(
    ffmpeg: str,
    args: list[str],
    duration: float = 0.0,
    on_progress=None,
    cancel: threading.Event | None = None,
    cwd: str | None = None,
) -> RunResult:
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats", *args]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, cwd=cwd, creationflags=CREATE_NO_WINDOW,
    )
    tail: deque[str] = deque(maxlen=60)

    def _drain():
        for line in proc.stderr:
            try:
                tail.append(line.decode("utf-8", "replace").rstrip())
            except Exception:
                pass

    t = threading.Thread(target=_drain, daemon=True)
    t.start()

    cancelled = False
    try:
        for line in proc.stdout:
            if cancel is not None and cancel.is_set():
                cancelled = True
                proc.terminate()
                break
            text = line.decode("utf-8", "replace").strip()
            if text.startswith("out_time_us=") and duration > 0 and on_progress:
                try:
                    us = int(text.split("=", 1)[1])
                    on_progress(max(0.0, min(0.999, us / 1_000_000 / duration)))
                except Exception:
                    pass
            elif text.startswith("progress=end") and on_progress:
                on_progress(1.0)
    finally:
        try:
            proc.wait(timeout=30)
        except Exception:
            proc.kill()
        t.join(timeout=5)

    ok = proc.returncode == 0 and not cancelled
    return RunResult(ok=ok, code=proc.returncode or 0, stderr="\n".join(tail), cancelled=cancelled)
