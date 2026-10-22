"""主界面。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox, QFileDialog,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter, QStackedWidget,
    QToolButton,
    QVBoxLayout, QWidget,
)

from . import config as cfgmod
from . import gif as gifmod
from .ffmpeg_tools import find_tools, is_bundled, probe
from .watermark import POSITIONS, POS_LABEL, WatermarkSpec, VIDEO_EXTS
from .worker import BatchWorker

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
MODES = ("video_wm", "image_wm", "gif")
OUT_KEYS = {"video_wm": "output_dir_video", "image_wm": "output_dir_image", "gif": "output_dir_gif"}

QSS = """
* { font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"; font-size: 13px; }
QWidget { color: #e7eaf0; }
QMainWindow, #Root { background: #131519; }
QScrollArea, QScrollArea > QWidget > QWidget, QStackedWidget { background: transparent; }
#Header { background: #171a1f; border-bottom: 1px solid #22262e; }
#Title { font-size: 17px; font-weight: 600; }
#Sub { color: #7d8695; font-size: 12px; }
#Chip { color: #7ee2b8; background: #16241d; border: 1px solid #21402f; border-radius: 9px; padding: 3px 9px; font-size: 12px; }
#ChipBad { color: #ff9a8b; background: #2a1a18; border: 1px solid #43241f; border-radius: 9px; padding: 3px 9px; font-size: 12px; }
QGroupBox { border: 1px solid #242933; border-radius: 10px; margin-top: 14px; padding: 12px 10px 10px 10px; background: #171a1f; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #93a0b2; font-size: 12px; }
QPushButton { background: #1d2129; border: 1px solid #2b313c; border-radius: 8px; padding: 7px 14px; color: #dfe4ec; }
QPushButton:hover { background: #242a34; border-color: #3a4250; }
QPushButton:pressed { background: #1a1e25; }
QPushButton:disabled { color: #5c646f; background: #191c22; border-color: #23272f; }
QPushButton:checked { background: #1b3357; border-color: #3d6db3; color: #cfe0ff; }
#Primary { background: #3f7fe0; border: none; color: white; font-weight: 600; padding: 9px 22px; border-radius: 9px; }
#Primary:hover { background: #4b8bea; }
#Primary:disabled { background: #2a3443; color: #6d7787; }
#Danger { background: #2a1c1c; border-color: #4a2a2a; color: #ffb3a7; }
QLineEdit, QPlainTextEdit, QComboBox { background: #101317; border: 1px solid #262b35; border-radius: 7px; padding: 6px 8px; selection-background-color: #2f5f9e; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #3d6db3; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView { background: #171a1f; border: 1px solid #2b313c; selection-background-color: #24395c; }
QListWidget { background: #101317; border: 1px solid #242933; border-radius: 9px; padding: 4px; }
QListWidget::item { padding: 7px 8px; border-radius: 6px; color: #d7dce6; }
QListWidget::item:selected { background: #1e2a3d; color: #eaf1ff; }
QListWidget::item:hover { background: #1a1e25; }
QSlider::groove:horizontal { height: 4px; background: #262b35; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; background: #5c93e8; }
QSlider::sub-page:horizontal { background: #3d6db3; border-radius: 2px; }
QSlider::handle:horizontal:disabled { background: #3a4250; }
QSlider::sub-page:horizontal:disabled { background: #2a303a; }
QSlider::groove:horizontal:disabled { background: #20242c; }
QProgressBar { background: #101317; border: 1px solid #242933; border-radius: 7px; height: 16px; text-align: center; color: #cbd3df; font-size: 11px; }
QProgressBar::chunk { background: #3f7fe0; border-radius: 6px; }
QSplitter::handle { background: #1b1f26; }
#PosBtn { font-size: 15px; padding: 0; background: #14171c; border: 1px solid #262b35; border-radius: 8px; color: #96a1b1; }
#PosBtn:hover { border-color: #3a4250; color: #d6dee9; }
#PosBtn:checked { background: #1c3660; border-color: #4b86d8; color: #dbe8ff; }
#Hint { color: #7d8695; font-size: 12px; }
#Zoom { background: #1a1e25; border-color: #2b313c; padding: 10px 0; font-size: 13px; }
#Zoom:checked { background: #1c3660; border-color: #4b86d8; color: #dbe8ff; font-weight: 600; }
QCheckBox { color: #b9c2cf; spacing: 6px; }
QCheckBox::indicator { width: 15px; height: 15px; border-radius: 4px; border: 1px solid #333a46; background: #101317; }
QCheckBox::indicator:hover { border-color: #4b8bea; }
QCheckBox::indicator:checked { background: #3f7fe0; border-color: #3f7fe0; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #2c3340; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #3a4354; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; }
QScrollBar::handle:horizontal { background: #2c3340; border-radius: 4px; min-width: 24px; }
"""


# --------------------------------------------------------------------- 组件

class PositionGrid(QWidget):
    changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        glyphs = {"tl": "↖", "tc": "↑", "tr": "↗", "cl": "←", "c": "•",
                  "cr": "→", "bl": "↙", "bc": "↓", "br": "↘"}
        self.buttons: dict[str, QToolButton] = {}
        for i, key in enumerate(POSITIONS):
            b = QToolButton()
            b.setObjectName("PosBtn")
            b.setText(glyphs[key])
            b.setToolTip(POS_LABEL[key])
            b.setCheckable(True)
            b.setFixedSize(44, 38)
            b.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
            self.group.addButton(b)
            self.buttons[key] = b
            grid.addWidget(b, i // 3, i % 3)
        grid.setColumnStretch(3, 1)
        self.set_value("br")

    def value(self) -> str:
        for k, b in self.buttons.items():
            if b.isChecked():
                return k
        return "br"

    def set_value(self, key: str):
        self.buttons.get(key, self.buttons["br"]).setChecked(True)


class FileQueue(QListWidget):
    dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DropOnly)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setMinimumWidth(300)
        self.setAlternatingRowColors(False)
        self.setWordWrap(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.dropped.emit(paths)
            e.acceptProposedAction()

    def paths(self) -> list[str]:
        out = []
        for i in range(self.count()):
            p = self.item(i).data(Qt.UserRole)
            if p:
                out.append(p)
        return out

    def show_placeholder(self, text: str):
        if self.count():
            return
        it = QListWidgetItem(text)
        it.setFlags(Qt.NoItemFlags)
        it.setForeground(QColor("#5b6472"))
        it.setTextAlignment(Qt.AlignCenter)
        self.addItem(it)
        self._ph = it

    def clear_placeholder(self):
        ph = getattr(self, "_ph", None)
        if ph is not None:
            row = self.row(ph)
            if row >= 0:
                self.takeItem(row)
            self._ph = None


class WatermarkPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # --- 水印类型（组合成一行，节省纵向空间）
        box_type = QGroupBox("水印内容")
        v = QHBoxLayout(box_type)
        v.setSpacing(8)
        self.type_group = QButtonGroup(self)
        self.type_group.setExclusive(True)
        self.btn_text = QPushButton("文字")
        self.btn_img = QPushButton("图片")
        for b in (self.btn_text, self.btn_img):
            b.setCheckable(True)
            b.setFixedSize(54, 28)
            self.type_group.addButton(b)
        self.btn_text.setChecked(True)
        self.btn_text.clicked.connect(self._sync_type)
        self.btn_img.clicked.connect(self._sync_type)
        v.addWidget(self.btn_text)
        v.addWidget(self.btn_img)

        self.stack = QStackedWidget()
        # 文字页
        page_text = QWidget()
        pt = QHBoxLayout(page_text)
        pt.setContentsMargins(0, 0, 0, 0)
        pt.setSpacing(8)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("输入水印文字，可换行，例如：© 2026 我的工作室")
        self.text_edit.setFixedHeight(58)
        self.color_btn = QPushButton("#FFFFFF")
        self.color_btn.setFixedWidth(96)
        self.color_btn.setFixedHeight(28)
        self.color_btn.setToolTip("文字颜色")
        self.color_btn.clicked.connect(self._pick_color)
        pt.addWidget(self.text_edit, 1)
        pt.addWidget(self.color_btn)
        self.stack.addWidget(page_text)

        # 图片页
        page_img = QWidget()
        pi = QHBoxLayout(page_img)
        pi.setContentsMargins(0, 0, 0, 0)
        pi.setSpacing(8)
        self.img_btn = QPushButton("选择水印图片…")
        self.img_btn.clicked.connect(self._pick_image)
        self._image_path = ""
        self.img_label = QLabel("未选择（推荐透明 PNG）")
        self.img_label.setObjectName("Hint")
        self.img_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        pi.addWidget(self.img_btn)
        pi.addWidget(self.img_label, 1)
        pi.addStretch(0)
        self.stack.addWidget(page_img)
        v.addWidget(self.stack, 1)
        lay.addWidget(box_type)

        # --- 位置 + 参数（左右并排，避免面板过高）
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        box_pos = QGroupBox("水印位置")
        vpos = QVBoxLayout(box_pos)
        vpos.setSpacing(6)
        self.pos = PositionGrid()
        vpos.addWidget(self.pos)
        self.pos_hint = QLabel("右下")
        self.pos_hint.setObjectName("Hint")
        self.pos_hint.setAlignment(Qt.AlignCenter)
        vpos.addWidget(self.pos_hint)
        vpos.addStretch(1)
        box_pos.setFixedWidth(180)
        bottom.addWidget(box_pos)

        box_p = QGroupBox("参数")
        vp = QVBoxLayout(box_p)
        vp.setSpacing(6)
        self.s_scale, self.l_scale, w1 = self._slider("水印大小", 2, 40, 12, "% 短边")
        self.s_font, self.l_font, w2 = self._slider("字号", 1, 15, 4, "% 高度")
        self.s_opacity, self.l_opacity, w3 = self._slider("不透明度", 0, 100, 80, "%")
        self.s_margin, self.l_margin, w4 = self._slider("边距", 0, 10, 3, "% 短边")
        for w in (w1, w2, w3, w4):
            vp.addWidget(w)
        vp.addStretch(1)
        bottom.addWidget(box_p, 1)
        lay.addLayout(bottom)
        note = QLabel("输出保持原始分辨率、帧率与音轨；CRF 18 近无损编码，肉眼看不出画质差异。")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch(1)

        self._sync_type()

    def _slider(self, title: str, lo: int, hi: int, val: int, suffix: str):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        t = QLabel(title)
        t.setFixedWidth(64)
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        lab = QLabel(f"{val}{suffix}")
        lab.setFixedWidth(70)
        lab.setObjectName("Hint")
        s.valueChanged.connect(lambda v: lab.setText(f"{v}{suffix}"))
        h.addWidget(t)
        h.addWidget(s, 1)
        h.addWidget(lab)
        return s, lab, row

    # ---------------------------------------------------------------- 行为
    def _sync_type(self):
        is_text = self.btn_text.isChecked()
        self.stack.setCurrentIndex(0 if is_text else 1)
        self.s_font.setEnabled(is_text)
        self.s_scale.setEnabled(not is_text)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.color_btn.text()), self, "选择文字颜色")
        if c.isValid():
            self.color_btn.setText(c.name().upper())
            self.color_btn.setStyleSheet(
                f"color:{'#111' if c.lightness() > 140 else '#fff'};background:{c.name()};"
                "border:1px solid #2b313c;border-radius:7px;padding:5px 10px;"
            )

    def _pick_image(self):
        start = str(Path(self._image_path).parent) if self._image_path else ""
        f, _ = QFileDialog.getOpenFileName(
            self, "选择水印图片", start, "图片 (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if f:
            self.set_image(f)

    def set_image(self, path: str):
        self._image_path = path
        self.img_label.setText(Path(path).name)
        self.img_label.setToolTip(path)
        self.btn_img.setChecked(True)
        self._sync_type()

    def set_text(self, text: str):
        self.text_edit.setPlainText(text)

    def spec(self) -> WatermarkSpec:
        return WatermarkSpec(
            kind="text" if self.btn_text.isChecked() else "image",
            text=self.text_edit.toPlainText(),
            image=self._image_path,
            position=self.pos.value(),
            scale_pct=self.s_scale.value(),
            font_pct=self.s_font.value(),
            opacity=self.s_opacity.value(),
            margin_pct=self.s_margin.value(),
            color=self.color_btn.text(),
        )

    def load(self, cfg: dict):
        img_saved = cfg.get("watermark_image") or ""
        want_image = cfg.get("wm_type", "text") != "text"
        (self.btn_img if want_image else self.btn_text).setChecked(True)
        self.text_edit.setPlainText(cfg.get("text", ""))
        if img_saved:
            self._image_path = img_saved
            self.img_label.setText(Path(img_saved).name)
            self.img_label.setToolTip(img_saved)
        self.pos.set_value(cfg.get("position", "br"))
        self.pos_hint.setText(POS_LABEL.get(cfg.get("position", "br"), "右下"))
        self.s_scale.setValue(int(cfg.get("scale_pct", 12)))
        self.s_font.setValue(int(cfg.get("font_pct", 4)))
        self.s_opacity.setValue(int(cfg.get("opacity", 80)))
        self.s_margin.setValue(int(cfg.get("margin_pct", 3)))
        self.color_btn.setText(cfg.get("color", "#FFFFFF"))
        self._sync_type()

    def store(self, cfg: dict):
        s = self.spec()
        cfg.update({
            "wm_type": s.kind, "text": s.text, "watermark_image": s.image,
            "position": s.position, "scale_pct": s.scale_pct, "font_pct": s.font_pct,
            "opacity": s.opacity, "margin_pct": s.margin_pct, "color": s.color,
        })


class GifPanel(QWidget):
    percent_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        box = QGroupBox("输出分辨率")
        v = QVBoxLayout(box)
        v.setSpacing(10)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[int, QPushButton] = {}
        for p in gifmod.PERCENTS:
            b = QPushButton(f"{p}%")
            b.setObjectName("Zoom")
            b.setCheckable(True)
            b.setMinimumHeight(46)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.clicked.connect(lambda _=False, val=p: self._select(val))
            self.group.addButton(b)
            self.buttons[p] = b
            row.addWidget(b)
        v.addLayout(row)
        self.zoom_hint = QLabel("相对于原视频尺寸缩放，长宽比不变")
        self.zoom_hint.setObjectName("Hint")
        v.addWidget(self.zoom_hint)
        lay.addWidget(box)

        box2 = QGroupBox("说明")
        v2 = QVBoxLayout(box2)
        for text in (
            "• 帧率保持原视频不变（上限 50fps，GIF 帧延迟最小 1/100 秒）",
            "• 使用 Lanczos 缩放 + 双遍调色板，画质优先",
            "• 高分辨率长视频的 GIF 体积会很大，建议 60%~80%",
        ):
            lab = QLabel(text)
            lab.setWordWrap(True)
            lab.setObjectName("Hint")
            v2.addWidget(lab)
        lay.addWidget(box2)
        lay.addStretch(1)

    def _select(self, p: int):
        self.percent_changed.emit(p)

    def value(self) -> int:
        for p, b in self.buttons.items():
            if b.isChecked():
                return p
        return 80

    def set_value(self, p: int, notify: bool = False):
        (self.buttons.get(p) or self.buttons[80]).setChecked(True)
        if notify:
            self.percent_changed.emit(self.value())


# --------------------------------------------------------------------- 主窗口

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = cfgmod.load()
        self.ffmpeg, self.ffprobe = find_tools()
        self.worker: BatchWorker | None = None
        self.mode = "video_wm"

        self.setWindowTitle("水印工坊 · 批量水印与 GIF 转换")
        icon = resource_path("assets/icon.png")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1180, 800)
        self.setAcceptDrops(True)
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.setSpacing(12)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_left())
        split.addWidget(self._build_right())
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([520, 620])
        bl.addWidget(split, 1)
        bl.addWidget(self._build_actionbar())
        outer.addWidget(body, 1)

        self._restore()
        self._sync_mode()
        self._update_env_chip()

    # ---------------------------------------------------------------- 构建
    def _build_header(self) -> QWidget:
        w = QFrame()
        w.setObjectName("Header")
        h = QHBoxLayout(w)
        h.setContentsMargins(18, 12, 18, 12)
        h.setSpacing(12)
        t = QLabel("水印工坊")
        t.setObjectName("Title")
        s = QLabel("批量视频/图片水印 · 视频转 GIF")
        s.setObjectName("Sub")
        h.addWidget(t)
        h.addWidget(s)
        h.addStretch(1)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons: dict[str, QPushButton] = {}
        for key, label in (("video_wm", "视频加水印"), ("image_wm", "图片加水印"), ("gif", "视频转 GIF")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setMinimumWidth(104)
            b.clicked.connect(lambda _=False, k=key: self._switch_mode(k))
            self.mode_group.addButton(b)
            self.mode_buttons[key] = b
            h.addWidget(b)
        self.mode_buttons["video_wm"].setChecked(True)

        self.env_chip = QLabel("ffmpeg 检测中")
        if self.ffmpeg:
            self.env_chip.setToolTip(
                ("内置 ffmpeg：" if is_bundled(self.ffmpeg) else "系统 ffmpeg：") + self.ffmpeg
            )
        self.env_chip.setObjectName("Chip")
        h.addSpacing(6)
        h.addWidget(self.env_chip)
        return w

    def _build_left(self) -> QWidget:
        box = QGroupBox("待处理文件")
        v = QVBoxLayout(box)
        v.setSpacing(8)
        self.queue = FileQueue()
        self.queue.dropped.connect(self._on_dropped)
        self.queue.setToolTip("把文件或整个文件夹拖到这里")
        v.addWidget(self.queue, 1)

        row = QHBoxLayout()
        b_add = QPushButton("添加文件")
        b_add.clicked.connect(self._add_files)
        b_dir = QPushButton("添加文件夹")
        b_dir.clicked.connect(self._add_folder)
        b_clr = QPushButton("清空")
        b_clr.clicked.connect(self._clear)
        row.addWidget(b_add)
        row.addWidget(b_dir)
        row.addStretch(1)
        row.addWidget(b_clr)
        v.addLayout(row)

        self.queue_info = QLabel("拖入文件或文件夹，支持批量")
        self.queue_info.setObjectName("Hint")
        v.addWidget(self.queue_info)
        return box

    def _build_right(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        self.pages = QStackedWidget()
        self.wm_panel = WatermarkPanel()
        self.wm_panel.pos.changed.connect(
            lambda k: self.wm_panel.pos_hint.setText(POS_LABEL.get(k, ""))
        )
        self.gif_panel = GifPanel()
        self.gif_panel.set_value(int(self.cfg.get("gif_percent", 80)))
        self.gif_panel.percent_changed.connect(self._on_percent)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.wm_panel)
        scroll.setMinimumHeight(120)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        self.pages.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        self.pages.addWidget(scroll)
        self.pages.addWidget(self.gif_panel)
        v.addWidget(self.pages, 1)

        # 输出目录
        box_out = QGroupBox("输出位置")
        ho = QHBoxLayout(box_out)
        ho.setSpacing(8)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("选择输出文件夹（会自动记住）")
        self.out_edit.setReadOnly(True)
        b_browse = QPushButton("浏览…")
        b_browse.clicked.connect(self._pick_out)
        b_open = QPushButton("打开")
        b_open.clicked.connect(self._open_out)
        ho.addWidget(self.out_edit, 1)
        ho.addWidget(b_browse)
        ho.addWidget(b_open)
        v.addWidget(box_out)

        # 日志
        box_log = QGroupBox("处理日志")
        vl = QVBoxLayout(box_log)
        vl.setContentsMargins(8, 6, 8, 8)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(74)
        self.log_view.setPlaceholderText("这里会显示处理结果与错误信息")
        vl.addWidget(self.log_view)
        v.addWidget(box_log)
        return w

    def _build_actionbar(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        self.status = QLabel("就绪")
        self.status.setObjectName("Hint")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(230)
        self.progress.setFormat("%p%")
        self.open_check = QCheckBox("完成后打开输出目录")
        self.open_check.setChecked(bool(self.cfg.get("open_after", True)))
        self.start_btn = QPushButton("开始处理")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        h.addWidget(self.status, 1)
        h.addWidget(self.open_check)
        h.addWidget(self.progress)
        h.addWidget(self.cancel_btn)
        h.addWidget(self.start_btn)
        return w

    # ---------------------------------------------------------------- 状态
    def _out_key(self, mode: str | None = None) -> str:
        return OUT_KEYS.get(mode or self.mode, "output_dir_video")

    def _restore(self):
        self.wm_panel.load(self.cfg)
        self.out_edit.setText(self.cfg.get(self._out_key(), ""))
        geo = self.cfg.get("ui_geometry")
        if geo:
            try:
                import base64
                self.restoreGeometry(base64.b64decode(geo.encode()))
            except Exception:
                pass

    def _save_cfg(self):
        self.wm_panel.store(self.cfg)
        self.cfg[self._out_key()] = self.out_edit.text().strip()
        self.cfg["gif_percent"] = self.gif_panel.value()
        self.cfg["open_after"] = self.open_check.isChecked()
        try:
            import base64
            self.cfg["ui_geometry"] = base64.b64encode(bytes(self.saveGeometry())).decode()
        except Exception:
            pass
        cfgmod.save(self.cfg)

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            if QMessageBox.question(self, "正在处理", "任务还在进行，确定退出？") != QMessageBox.Yes:
                e.ignore()
                return
            self.worker.cancel()
            self.worker.wait(3000)
        self._save_cfg()
        super().closeEvent(e)

    def _update_env_chip(self):
        if self.ffmpeg:
            self.env_chip.setText("ffmpeg 已就绪")
            self.env_chip.setObjectName("Chip")
        else:
            self.env_chip.setText("未找到 ffmpeg")
            self.env_chip.setObjectName("ChipBad")
        self.env_chip.style().unpolish(self.env_chip)
        self.env_chip.style().polish(self.env_chip)

    # ---------------------------------------------------------------- 模式
    def _switch_mode(self, key: str):
        if key == self.mode:
            return
        # 切走前把当前模式的输出目录存回它自己的槽位
        self.cfg[self._out_key()] = self.out_edit.text().strip()
        self.mode = key
        self._sync_mode()
        self.out_edit.setText(self.cfg.get(self._out_key(), ""))
        self._update_queue_info()

    def _sync_mode(self):
        self.mode_buttons[self.mode].setChecked(True)
        is_gif = self.mode == "gif"
        self.pages.setCurrentIndex(1 if is_gif else 0)
        removed = self._prune_queue()
        self._update_queue_info(f"已移除 {removed} 个不适用于当前模式的文件" if removed else "")
        if is_gif:
            QTimer.singleShot(0, self._update_gif_example)

    def _allowed_exts(self) -> set[str]:
        return IMAGE_EXTS if self.mode == "image_wm" else VIDEO_EXTS

    def _prune_queue(self) -> int:
        exts = self._allowed_exts()
        removed = 0
        for i in reversed(range(self.queue.count())):
            p = self.queue.item(i).data(Qt.UserRole)
            if p and Path(p).suffix.lower() not in exts:
                self.queue.takeItem(i)
                removed += 1
        return removed

    def _on_percent(self, p: int):
        self.cfg["gif_percent"] = p
        self._update_gif_example()

    # ---------------------------------------------------------------- 文件
    def _add_paths(self, paths: list[str]):
        exts = self._allowed_exts()
        found: list[str] = []
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                found += [str(f) for f in sorted(p.rglob("*")) if f.suffix.lower() in exts]
            elif p.is_file() and p.suffix.lower() in exts:
                found.append(str(p))
        exist = {os.path.normcase(x) for x in self.queue.paths()}
        added = 0
        for f in found:
            if os.path.normcase(f) in exist:
                continue
            item = QListWidgetItem(Path(f).name)
            item.setData(Qt.UserRole, f)
            item.setToolTip(f)
            self.queue.addItem(item)
            exist.add(os.path.normcase(f))
            added += 1
        if added and not self.out_edit.text().strip():
            guess = str(Path(found[0]).parent / "输出")
            self.out_edit.setText(guess)
            self.cfg[self._out_key()] = guess
        self._update_queue_info(f"新增 {added} 个文件" if added else "没有找到可处理的文件")
        if added and self.mode == "gif":
            QTimer.singleShot(10, self._update_gif_example)

    def _on_dropped(self, paths: list[str]):
        self._add_paths(paths)

    def _add_files(self):
        exts = self._allowed_exts()
        pattern = " ".join(f"*{e}" for e in sorted(exts))
        start = self.cfg.get("last_input_dir", "")
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件", start, f"媒体文件 ({pattern})")
        if files:
            self.cfg["last_input_dir"] = str(Path(files[0]).parent)
            self._add_paths(files)

    def _add_folder(self):
        start = self.cfg.get("last_input_dir", "")
        d = QFileDialog.getExistingDirectory(self, "选择文件夹", start)
        if d:
            self.cfg["last_input_dir"] = d
            self._add_paths([d])

    def _clear(self):
        self.queue.clear()
        self._update_queue_info()

    def _update_queue_info(self, extra: str = ""):
        if self.queue.paths():
            self.queue.clear_placeholder()
        else:
            self.queue.show_placeholder("把文件或整个文件夹拖到这里\n或点击下方「添加文件」")
        n = len(self.queue.paths())
        kind = {"video_wm": "视频", "image_wm": "图片", "gif": "视频"}[self.mode]
        text = f"共 {n} 个{kind}文件" if n else "拖入文件或文件夹，支持批量"
        if extra:
            text += f" · {extra}"
        self.queue_info.setText(text)

    def _update_gif_example(self):
        if not self.ffprobe or not self.queue.paths():
            self.gif_panel.zoom_hint.setText("相对于原视频尺寸缩放，长宽比不变")
            return
        try:
            info = probe(self.ffprobe, self.queue.paths()[0])
            p = self.gif_panel.value()
            w, h = gifmod.gif_size(info, p)
            fps = min(info.fps, gifmod.MAX_FPS)
            self.gif_panel.zoom_hint.setText(
                f"按 {p}% 输出示例：{info.width}×{info.height} → {w}×{h} · {fps:.1f}fps"
            )
        except Exception:
            pass

    # ---------------------------------------------------------------- 输出
    def _pick_out(self):
        d = QFileDialog.getExistingDirectory(
            self, "选择输出文件夹", self.out_edit.text() or self.cfg.get("last_input_dir", "")
        )
        if d:
            self.out_edit.setText(d)
            self._update_queue_info("输出位置已更新")

    def _open_out(self):
        d = self.out_edit.text().strip()
        if d and Path(d).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))
        else:
            QMessageBox.information(self, "提示", "输出文件夹还不存在，处理完成后会自动创建。")

    # ---------------------------------------------------------------- 执行
    def _start(self):
        if not self.ffmpeg:
            QMessageBox.warning(self, "缺少 ffmpeg", "未检测到 ffmpeg，请把 ffmpeg 放到程序目录的 ffmpeg\\bin 下，或加入 PATH。")
            return
        files = self.queue.paths()
        if not files:
            QMessageBox.information(self, "没有文件", "请先添加要处理的文件或文件夹。")
            return
        out_dir = self.out_edit.text().strip()
        if not out_dir:
            QMessageBox.information(self, "缺少输出位置", "请选择输出文件夹。")
            return
        spec = self.wm_panel.spec()
        if self.mode != "gif":
            if spec.kind == "text" and not spec.text.strip():
                QMessageBox.information(self, "水印为空", "请输入水印文字，或切换为图片水印。")
                return
            if spec.kind == "image" and (not spec.image or not Path(spec.image).exists()):
                QMessageBox.information(self, "水印图片无效", "请选择一张存在的图片作为水印。")
                return
        try:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "输出目录不可用", str(exc))
            return

        self._save_cfg()
        self.log_view.clear()
        self.progress.setValue(0)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status.setText("正在处理…")
        for i in range(self.queue.count()):
            self.queue.item(i).setForeground(QColor("#d7dce6"))

        self.worker = BatchWorker(
            self.mode, files, out_dir, spec, self.gif_panel.value(),
            self.ffmpeg, self.ffprobe, self,
        )
        self.worker.file_started.connect(self._on_file_start)
        self.worker.progress.connect(lambda p: self.progress.setValue(int(p * 100)))
        self.worker.file_done.connect(self._on_file_done)
        self.worker.log.connect(lambda s: self.log_view.appendPlainText(s))
        self.worker.done.connect(self._on_all_done)
        self.worker.start()

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self.status.setText("正在取消…")
            self.cancel_btn.setEnabled(False)

    def _on_file_start(self, idx: int, name: str):
        self.status.setText(f"正在处理：{name}")
        if idx < self.queue.count():
            self.queue.setCurrentRow(idx)

    def _on_file_done(self, idx: int, ok: bool, msg: str):
        if idx < self.queue.count():
            item = self.queue.item(idx)
            item.setForeground(QColor("#7ee2b8" if ok else "#ff8f7d"))
            item.setText(("✓ " if ok else "✗ ") + Path(item.data(Qt.UserRole)).name)
            item.setToolTip(msg)

    def _on_all_done(self, ok: int, fail: int):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100 if fail == 0 and ok > 0 else self.progress.value())
        text = f"完成：成功 {ok} 个" + (f"，失败 {fail} 个" if fail else "")
        self.status.setText(text)
        self.log_view.appendPlainText(text)
        if ok and self.open_check.isChecked():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.out_edit.text().strip()))

    # ---------------------------------------------------------------- 拖拽
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self._add_paths(paths)


def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel


def run():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("水印工坊")
    icon = resource_path("assets/icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    return app.exec()
