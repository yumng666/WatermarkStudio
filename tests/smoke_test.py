"""端到端冒烟测试：生成素材 → 三种流程处理 → 校验输出参数。

运行：python tests/smoke_test.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mtool import gif as gifmod  # noqa: E402
from mtool import watermark as wm  # noqa: E402
from mtool.ffmpeg_tools import find_tools, probe, run_ffmpeg  # noqa: E402

FF, FP = find_tools()
ok_all = True


def check(label: str, cond: bool, detail: str = ""):
    global ok_all
    print(("PASS " if cond else "FAIL ") + label + (f"  ({detail})" if detail else ""))
    if not cond:
        ok_all = False


def make_source(tmp: Path) -> Path:
    src = tmp / "src.mp4"
    cmd = [
        FF, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(src),
    ]
    subprocess.run(cmd, check=True, creationflags=0x08000000)
    return src


def make_logo(tmp: Path) -> Path:
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (400, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 399, 159], radius=24, fill=(255, 92, 92, 230))
    d.text((40, 60), "WATERMARK", fill=(255, 255, 255, 255))
    p = tmp / "logo.png"
    img.save(p)
    return p


def main():
    if not FF or not FP:
        print("未找到 ffmpeg")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="mtool_test_"))
    print("临时目录:", tmp)
    src = make_source(tmp)
    logo = make_logo(tmp)
    info = probe(FP, str(src))
    print(f"源: {info.width}x{info.height} {info.fps:.2f}fps {info.pix_fmt} audio={info.has_audio}")
    check("源参数", info.width == 1280 and abs(info.fps - 30) < 0.1, f"{info.width}x{info.height}@{info.fps:.2f}")

    # 1) 视频 + 图片水印
    spec = wm.WatermarkSpec(kind="image", image=str(logo), position="br",
                            scale_pct=14, opacity=85, margin_pct=3)
    out1 = wm.output_path(str(src), str(tmp), "_wm_img")
    a1, wd1 = wm.build_video_args(info, spec, out1)
    res = run_ffmpeg(FF, a1, cwd=wd1)
    if wd1:
        shutil.rmtree(wd1, ignore_errors=True)
    check("视频图片水印 成功", res.ok)
    if res.ok:
        i1 = probe(FP, out1)
        check("视频图片水印 分辨率不变", (i1.width, i1.height) == (1280, 720), f"{i1.width}x{i1.height}")
        check("视频图片水印 帧率不变", abs(i1.fps - 30) < 0.1, f"{i1.fps:.2f}")
        check("视频图片水印 音轨保留", i1.has_audio)
        check("视频图片水印 体积合理", Path(out1).stat().st_size > 40_000,
              f"{Path(out1).stat().st_size/1024:.0f}KB")

    # 2) 视频 + 文字水印（中文）
    spec2 = wm.WatermarkSpec(kind="text", text="© 2026 测试水印\n第二行", position="tl",
                             font_pct=5, opacity=80, margin_pct=3, color="#FFFFFF")
    out2 = wm.output_path(str(src), str(tmp), "_wm_txt")
    a2, wd2 = wm.build_video_args(info, spec2, out2)
    res2 = run_ffmpeg(FF, a2, cwd=wd2)
    if wd2:
        shutil.rmtree(wd2, ignore_errors=True)
    if not res2.ok:
        print(res2.stderr[-2000:])
    check("视频文字水印 成功", res2.ok)
    if res2.ok:
        i2 = probe(FP, out2)
        check("视频文字水印 参数不变", (i2.width, i2.height) == (1280, 720) and abs(i2.fps - 30) < 0.1)

    # 3) 图片水印
    from PIL import Image
    photo = tmp / "photo.jpg"
    Image.new("RGB", (1600, 1000), (28, 32, 40)).save(photo, quality=95)
    dst = wm.process_image(str(photo), str(tmp), spec2)
    im = Image.open(dst)
    check("图片文字水印 尺寸不变", im.size == (1600, 1000), str(im.size))
    check("图片水印 输出存在", Path(dst).exists())

    dst2 = wm.process_image(str(photo), str(tmp), spec)
    check("图片图片水印 尺寸不变", Image.open(dst2).size == (1600, 1000))

    # 4) GIF 80%
    outg = gifmod.gif_output_path(str(src), str(tmp))
    resg = run_ffmpeg(FF, gifmod.build_gif_args(info, 80, outg))
    if not resg.ok:
        print(resg.stderr[-2000:])
    check("GIF 转换成功", resg.ok)
    if resg.ok:
        g = Image.open(outg)
        check("GIF 尺寸 = 80%", g.size == (1024, 576), f"{g.size}")
        check("GIF 体积合理", Path(outg).stat().st_size > 30_000,
              f"{Path(outg).stat().st_size/1024:.0f}KB")

    # 5) GIF 60%
    outg2 = str(tmp / "out60.gif")
    resg2 = run_ffmpeg(FF, gifmod.build_gif_args(info, 60, outg2))
    if resg2.ok:
        check("GIF 尺寸 = 60%", Image.open(outg2).size == (768, 432), str(Image.open(outg2).size))

    print("\n结果:", "全部通过" if ok_all else "有失败项")
    print("输出目录:", tmp)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
