# 水印工坊 · 批量水印与 GIF 转换

一个本地运行的 Windows 桌面工具：批量给视频/图片加水印，批量把视频转成 GIF。界面中文，全部处理在本机完成，不联网。

![icon](assets/icon.png)

![视频加水印](shots/video-watermark.png)

## 功能

**1. 视频批量加水印**
- 支持文字水印和图片水印（PNG/JPG/WebP/BMP）
- 拖入多个文件或整个文件夹（含子目录）批量处理
- **保持原分辨率、原帧率、原音轨**：不做缩放、不变帧率、音频直接复制
- 编码用 libx264 `-crf 18 -preset medium`，属于"肉眼看不出差异"的近无损档（4K 批处理也不会太慢）
- 九宫格位置预设：左上/正上/右上/正左/居中/正右/左下/正下/右下
- 水印大小、字号、不透明度、边距都可调，尺寸按画面比例计算，混批不同分辨率也一致
- 输出容器跟随源文件（mp4/mov/mkv/avi），其他格式转 mp4

**2. 图片批量加水印**
- 参数与视频完全一致（同一套设置面板）
- JPEG 用 `quality=keep` 保存，避免二次压缩损失；PNG/WebP/TIFF 保留透明通道
- 保留 EXIF / ICC / DPI，自动处理手机照片方向

**3. 视频批量转 GIF**
- 分辨率按原片百分比输出：100% / 90% / 80% / 70% / 60%
- 帧率保持原片（上限 50fps，GIF 最小帧延迟为 1/100 秒）
- Lanczos 缩放 + 双遍调色板（palettegen/paletteuse），画质优先
- 比例不变，界面会实时显示"原始尺寸 → 输出尺寸"

**通用**
- 三种模式**各自记住自己的输出目录**（互不覆盖）；同时记住水印图片路径、上次输入目录、全部参数和窗口位置
- 水印类型也记忆：上次用图片水印，下次启动仍是图片水印面板
- 批量进度、逐个文件成功/失败标记、失败原因写进日志
- 可随时取消；失败自动重试（10bit→8bit、音频直通失败→AAC）
- 深色界面，九宫格位置按钮点选

## 直接用（免安装）

下载 `release/水印工坊-1.0.0-win64.zip`，解压后双击文件夹里的 `WatermarkStudio.exe`。

程序会按顺序找 ffmpeg：环境变量 `MTOOL_FFMPEG` → **exe 同级目录下的 `ffmpeg\bin\ffmpeg.exe`** → 系统 PATH → 常见安装路径。
想做成完全绿色版，把 ffmpeg 文件夹放到 exe 旁边即可：

```
水印工坊/
├─ WatermarkStudio.exe
├─ _internal/
└─ ffmpeg/bin/ffmpeg.exe   ← 可选，放这里就自带 ffmpeg
```

## 从源码运行

需要 Python 3.10+ 和 ffmpeg。

```bat
pip install -r requirements.txt
python main.py
```

或直接双击 `启动.bat`（会自动找 Python，用 pythonw 无控制台启动）。

### ffmpeg 怎么找

程序按以下顺序查找，找到第一个就用：

1. 环境变量 `MTOOL_FFMPEG`
2. 程序目录下 `ffmpeg\bin\ffmpeg.exe`（想做成绿色版就把 ffmpeg 放这里）
3. 系统 PATH
4. 常见安装路径（`C:\ffmpeg\bin`、`C:\Program Files\ffmpeg\bin` 等）

顶部右侧会显示"ffmpeg 已就绪 / 未找到 ffmpeg"。建议用 [BtbN](https://github.com/BtbN/FFmpeg-Builds/releases) 或 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 的完整构建。

## 目录结构

```
media-watermark-gif/
├─ main.py              入口
├─ 启动.bat             双击启动
├─ mtool/
│  ├─ ui.py             主界面（三模式、九宫格、拖拽队列）
│  ├─ worker.py         批处理线程（串行、进度、重试）
│  ├─ watermark.py      水印图层渲染 + ffmpeg 参数构建 + 图片合成
│  ├─ gif.py            视频转 GIF 参数构建
│  ├─ ffmpeg_tools.py   ffmpeg 定位 / ffprobe 探测 / 带进度执行
│  └─ config.py         配置持久化
├─ assets/icon.png
└─ tests/smoke_test.py  端到端自检（生成素材→三种流程→校验输出参数）
```

## 自检

```bat
python tests\smoke_test.py
```

会临时生成一段 1280x720@30fps 视频和一张透明 PNG，跑完三种流程后校验：输出分辨率、帧率、音轨、GIF 目标尺寸是否与预期一致。

## 一些实现说明

- **为什么水印必须重新编码**：overlay 是把水印烧进画面，无法流复制。所以"不压缩"落地为：分辨率/帧率/像素格式/音频流全部原样 + CRF 18 近无损编码。体积可能略增或略减，但画质肉眼看不出差别。
- **帧率保持**：输出不加 `-r`，并显式 `-fps_mode passthrough`，避免 VFR（手机拍摄）素材被强制转成固定帧率。
- **中文文字水印**：不用 ffmpeg 的 `drawtext`（多行对齐、转义都容易出问题），而是用 Pillow 先把文字渲染成紧贴文字的透明 PNG，再 overlay。视频和图片走同一套图层代码，所以两端输出完全一致。
- **水印尺寸自适应**：字号按画面高度百分比，图片水印宽度和边距按短边百分比，同一个参数在 4K 和 720p 上观感一致。
- **配置位置**：`%APPDATA%\MediaWatermarkTool\config.json`。三个模式分别对应 `output_dir_video` / `output_dir_image` / `output_dir_gif`，删掉这个文件即可恢复默认参数。

## 已知限制

- GIF 天生只有 256 色，渐变和肤色会有色带；高分辨率长视频体积仍然很大，建议 60%~80% + 短视频片段。
- HEIC/HEIF 图片需要先转换（Pillow 默认不支持）。
- 视频输出统一用 H.264；源是 ProRes/DNxHD 等中间格式时会转成 H.264。
- 水印位置是九宫格预设 + 边距微调，暂不支持鼠标自由拖拽。
