"""视频 / 图片水印：位置计算、滤镜构建、图片合成。"""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .ffmpeg_tools import MediaInfo

POSITIONS = ("tl", "tc", "tr", "cl", "c", "cr", "bl", "bc", "br")
POS_LABEL = {
    "tl": "左上", "tc": "正上", "tr": "右上",
    "cl": "正左", "c": "居中", "cr": "正右",
    "bl": "左下", "bc": "正下", "br": "右下",
}

FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".wmv", ".flv", ".webm",
              ".mpg", ".mpeg", ".ts", ".mts", ".3gp"}
SAFE_CONTAINERS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}


@dataclass
class WatermarkSpec:
    kind: str = "text"          # text | image
    text: str = ""
    image: str = ""
    position: str = "br"
    scale_pct: float = 12.0     # 图片水印宽度占短边百分比
    font_pct: float = 4.0       # 文字字号占高度百分比
    opacity: int = 80           # 0-100
    margin_pct: float = 3.0     # 边距占短边百分比
    color: str = "#FFFFFF"


def find_font() -> str | None:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _hex_rgba(color: str, opacity: int) -> tuple[int, int, int, int]:
    c = (color or "#FFFFFF").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except Exception:
        r = g = b = 255
    return r, g, b, max(0, min(100, int(opacity))) * 255 // 100


def pos_offset(frame: tuple[int, int], obj: tuple[int, int], spec: WatermarkSpec) -> tuple[int, int]:
    """九宫格定位：边距按画面短边百分比。"""
    m = max(0, round(min(frame) * spec.margin_pct / 100))
    pos = spec.position
    x = m if pos in ("tl", "cl", "bl") else (
        frame[0] - obj[0] - m if pos in ("tr", "cr", "br") else (frame[0] - obj[0]) // 2)
    y = m if pos in ("tl", "tc", "tr") else (
        frame[1] - obj[1] - m if pos in ("bl", "bc", "br") else (frame[1] - obj[1]) // 2)
    return x, y


def overlay_xy(pos: str, margin: int) -> tuple[str, str]:
    """ffmpeg overlay 坐标（W/H 主画面，w/h 水印）。"""
    m = margin
    table = {
        "tl": (f"{m}", f"{m}"),
        "tc": ("(W-w)/2", f"{m}"),
        "tr": (f"W-w-{m}", f"{m}"),
        "cl": (f"{m}", "(H-h)/2"),
        "c": ("(W-w)/2", "(H-h)/2"),
        "cr": (f"W-w-{m}", "(H-h)/2"),
        "bl": (f"{m}", f"H-h-{m}"),
        "bc": ("(W-w)/2", f"H-h-{m}"),
        "br": (f"W-w-{m}", f"H-h-{m}"),
    }
    return table.get(pos, table["br"])


# ---------------------------------------------------------------- 图层渲染

def _pil_font(size: int):
    from PIL import ImageFont
    path = find_font()
    if path:
        try:
            if path.lower().endswith(".ttc"):
                return ImageFont.truetype(path, size, index=0)
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def text_layer(size: tuple[int, int], spec: WatermarkSpec):
    """渲染紧贴文字的透明图层，返回 (图层, 左上角坐标)。"""
    from PIL import Image, ImageDraw

    font_px = max(8, round(size[1] * spec.font_pct / 100))
    font = _pil_font(font_px)
    stroke = max(1, round(font_px / 24))
    spacing = max(2, font_px // 5)
    fill = _hex_rgba(spec.color, spec.opacity)
    stroke_fill = (0, 0, 0, int(fill[3] * 0.35))
    text = spec.text or " "

    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = probe.multiline_textbbox((0, 0), text, font=font, spacing=spacing,
                                   stroke_width=stroke)
    pad = stroke + 2
    tw = max(1, bbox[2] - bbox[0])
    th = max(1, bbox[3] - bbox[1])
    layer = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(layer).multiline_text(
        (pad - bbox[0], pad - bbox[1]), text, font=font, fill=fill,
        spacing=spacing, stroke_width=stroke, stroke_fill=stroke_fill,
    )
    return layer, pos_offset(size, layer.size, spec)


def image_layer(size: tuple[int, int], spec: WatermarkSpec):
    from PIL import Image
    if not spec.image or not Path(spec.image).exists():
        raise RuntimeError("水印图片不存在")
    wm = Image.open(spec.image).convert("RGBA")
    target_w = max(8, round(min(size) * spec.scale_pct / 100))
    ratio = target_w / wm.width
    wm = wm.resize((target_w, max(1, round(wm.height * ratio))), Image.LANCZOS)
    if spec.opacity < 100:
        wm.putalpha(wm.getchannel("A").point(lambda v: v * spec.opacity // 100))
    return wm, pos_offset(size, wm.size, spec)


def render_layer(size: tuple[int, int], spec: WatermarkSpec):
    return image_layer(size, spec) if spec.kind == "image" else text_layer(size, spec)


# ---------------------------------------------------------------- 视频

def _pix_fmt_for(src: str) -> str:
    keep = {"yuv420p", "yuv422p", "yuv444p", "yuv420p10le", "yuv422p10le", "yuv444p10le"}
    if src in keep:
        return src
    return "yuv420p"


def build_video_args(info: MediaInfo, spec: WatermarkSpec,
                     out_path: str) -> tuple[list[str], str | None]:
    """返回 (ffmpeg 参数, 临时工作目录)。工作目录仅用于放中间图层，需调用方清理。"""
    margin = max(0, round(info.short_side * spec.margin_pct / 100))
    alpha = max(0.0, min(1.0, spec.opacity / 100))
    pix = _pix_fmt_for(info.pix_fmt)
    workdir: str | None = None
    args: list[str] = ["-i", info.path]

    if spec.kind == "image":
        if not spec.image or not Path(spec.image).exists():
            raise RuntimeError("水印图片不存在")
        wm_w = max(8, round(info.short_side * spec.scale_pct / 100))
        args += ["-i", spec.image]
        chain = (f"[1:v]scale={wm_w}:-1:flags=lanczos,format=rgba,"
                 f"colorchannelmixer=aa={alpha:.3f}[wm]")
    else:
        layer, _ = text_layer((info.width, info.height), spec)
        workdir = tempfile.mkdtemp(prefix="mtool_wm_")
        png = Path(workdir) / "text.png"
        layer.save(png)
        args += ["-i", str(png)]
        chain = "[1:v]format=rgba[wm]"

    x, y = overlay_xy(spec.position, margin)
    fc = f"{chain};[0:v][wm]overlay={x}:{y}:format=auto[v]"
    args += ["-filter_complex", fc, "-map", "[v]"]
    args += [
        "-map", "0:a?", "-map_metadata", "0", "-map_chapters", "0",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", pix,
        "-fps_mode", "passthrough", "-c:a", "copy",
        "-max_muxing_queue_size", "2048",
    ]
    if out_path.lower().endswith((".mp4", ".mov", ".m4v")):
        args += ["-movflags", "+faststart"]
    args += [out_path]
    return args, workdir


def output_path(src: str, out_dir: str, suffix: str = "_wm") -> str:
    p = Path(src)
    ext = p.suffix.lower()
    if ext not in SAFE_CONTAINERS:
        ext = ".mp4"
    return str(Path(out_dir) / f"{p.stem}{suffix}{ext}")


# ---------------------------------------------------------------- 图片

def process_image(src: str, out_dir: str, spec: WatermarkSpec, suffix: str = "_wm") -> str:
    from PIL import Image, ImageOps

    img = Image.open(src)
    exif = img.info.get("exif")
    icc = img.info.get("icc_profile")
    dpi = img.info.get("dpi")

    img = ImageOps.exif_transpose(img)
    base = img.convert("RGBA")
    layer, xy = render_layer(base.size, spec)
    base.alpha_composite(layer, xy)

    p = Path(src)
    ext = p.suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"):
        ext = ".png"
    dst = str(Path(out_dir) / f"{p.stem}{suffix}{ext}")

    kw: dict = {}
    if exif:
        kw["exif"] = exif
    if icc:
        kw["icc_profile"] = icc
    if dpi:
        kw["dpi"] = dpi

    if ext in (".jpg", ".jpeg"):
        out = base.convert("RGB")
        try:
            out.save(dst, "JPEG", quality="keep", subsampling="keep", **kw)
        except Exception:
            out.save(dst, "JPEG", quality=95, subsampling=0, **kw)
    elif ext == ".webp":
        base.save(dst, "WEBP", quality=95, method=4, **kw)
    elif ext in (".tif", ".tiff"):
        base.save(dst, "TIFF", **kw)
    elif ext == ".bmp":
        base.convert("RGB").save(dst, "BMP")
    else:
        base.save(dst, "PNG", **kw)
    return dst


def unique_temp() -> str:
    return tempfile.mkdtemp(prefix="mtool_")


def cleanup(path: str | None):
    if path:
        shutil.rmtree(path, ignore_errors=True)
