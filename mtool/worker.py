"""批处理线程：串行执行任务，回报进度与错误。"""
from __future__ import annotations

import dataclasses
import shutil
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import gif as gifmod
from . import watermark as wm
from .ffmpeg_tools import MediaInfo, probe, run_ffmpeg


class BatchWorker(QThread):
    file_started = Signal(int, str)
    progress = Signal(float)
    file_done = Signal(int, bool, str)
    log = Signal(str)
    done = Signal(int, int)

    def __init__(self, mode: str, files: list[str], out_dir: str,
                 spec: wm.WatermarkSpec, gif_percent: int,
                 ffmpeg: str, ffprobe: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.files = list(files)
        self.out_dir = out_dir
        self.spec = spec
        self.gif_percent = gif_percent
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    # ---------------------------------------------------------------- run
    def run(self):
        ok = fail = 0
        total = len(self.files)
        Path(self.out_dir).mkdir(parents=True, exist_ok=True)

        for idx, src in enumerate(self.files):
            if self.cancel_event.is_set():
                self.log.emit("已取消剩余任务")
                break
            self.file_started.emit(idx, Path(src).name)
            try:
                if self.mode == "image_wm":
                    dst = wm.process_image(src, self.out_dir, self.spec)
                    self.progress.emit((idx + 1) / total)
                    self.file_done.emit(idx, True, f"完成 → {Path(dst).name}")
                    ok += 1
                    continue

                info = probe(self.ffprobe, src)
                workdir = None
                if self.mode == "gif":
                    dst = gifmod.gif_output_path(src, self.out_dir)
                    args = gifmod.build_gif_args(info, self.gif_percent, dst)
                else:
                    dst = wm.output_path(src, self.out_dir)
                    args, workdir = wm.build_video_args(info, self.spec, dst)

                try:
                    res = self._run(info, args, idx, total)
                    if not res.ok and not res.cancelled:
                        res = self._retry(info, args, idx, total, res)
                finally:
                    if workdir:
                        shutil.rmtree(workdir, ignore_errors=True)

                if res.cancelled:
                    self.log.emit("已取消")
                    break
                if res.ok:
                    self.file_done.emit(idx, True, f"完成 → {Path(dst).name}")
                    ok += 1
                else:
                    self.file_done.emit(idx, False, self._last_error(res.stderr))
                    fail += 1
                    self.log.emit(f"[失败] {Path(src).name}\n{res.stderr[-1500:]}")
            except Exception as exc:
                self.file_done.emit(idx, False, str(exc))
                self.log.emit(f"[错误] {Path(src).name}: {exc}")
                fail += 1

        self.done.emit(ok, fail)

    # ---------------------------------------------------------------- helpers
    def _run(self, info: MediaInfo, args: list[str], idx: int, total: int,
             cwd: str | None = None):
        def _p(p: float):
            self.progress.emit((idx + p) / total)

        return run_ffmpeg(self.ffmpeg, args, duration=info.duration,
                          on_progress=_p, cancel=self.cancel_event, cwd=cwd)

    def _retry(self, info: MediaInfo, args: list[str], idx: int, total: int, first,
               cwd: str | None = None):
        """常见的两类兼容性失败：10bit 编码不被支持、音频无法直通。"""
        attempts: list[tuple[str, list[str], MediaInfo]] = []

        if ("-pix_fmt" in args and info.pix_fmt.endswith("10le")):
            i = args.index("-pix_fmt")
            a = list(args)
            a[i + 1] = "yuv420p"
            attempts.append(("10bit → 8bit", a, dataclasses.replace(info, pix_fmt="yuv420p")))

        if "-c:a" in args and args[args.index("-c:a") + 1] == "copy":
            a = list(args)
            i = a.index("-c:a")
            a[i + 1] = "aac"
            a[i + 2:i + 2] = ["-b:a", "192k"]
            attempts.append(("音频直通失败 → AAC 192k", a, info))

        for label, a, inf in attempts:
            self.log.emit(f"  重试（{label}）：{Path(info.path).name}")
            res = self._run(inf, a, idx, total, cwd)
            if res.ok or res.cancelled:
                return res
        return first

    @staticmethod
    def _last_error(stderr: str) -> str:
        lines = [ln for ln in (stderr or "").splitlines() if ln.strip()]
        return lines[-1][:300] if lines else "ffmpeg 处理失败"


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024
    return f"{num:.1f} GB"


def free_space(path: str) -> str:
    try:
        return human_size(shutil.disk_usage(path).free)
    except Exception:
        return "-"
