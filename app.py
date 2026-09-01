from __future__ import annotations

import random
import re
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from src import __version__
from src.ffmpeg_runner import FFmpegRunner, SUPPORTED_TRANSITIONS, find_ffmpeg
from src.image_maker import compose_collage, save_jpeg
from src.media import MediaSelector
from src.settings import load_settings, save_settings

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

PICK = {
    "每个目录各取1张": "separate",
    "所有启用目录混合随机": "mix",
    "全部从目录1抽取": "dir1",
    "全部从目录2抽取": "dir2",
    "全部从目录3抽取": "dir3",
    "全部从目录4抽取": "dir4",
}
CANVAS = {"9:16": (1080, 1920), "3:4": (1080, 1440), "16:9": (1920, 1080)}
TRANS = {
    "淡化": "fade",
    "左滑": "slideleft",
    "右滑": "slideright",
    "上滑": "slideup",
    "下滑": "slidedown",
    "溶解": "dissolve",
}
BG = ("#F4F7FB", "#0E1116")
CARD = ("#FFFFFF", "#171B22")
ALT = ("#F7F9FC", "#1D232C")
BORDER = ("#E2E8F0", "#303846")
TEXT = ("#17202B", "#F4F6F8")
MUTED = ("#687386", "#9AA6B5")
BLUE = ("#2563EB", "#3B82F6")
GREEN = ("#16A34A", "#22C55E")


def safe_name(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", value.strip()) or "游戏素材"


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.saved = load_settings()
        self.running = False
        self.preview_image = None
        self.title(f"ImageToAnimation  ·  v{__version__}")
        self.geometry("1360x900")
        self.minsize(1120, 760)
        self._vars()
        self._build_ui()
        self._restore()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _vars(self) -> None:
        s = self.saved
        dirs = (s.get("directories", []) + [""] * 4)[:4]
        self.output_mode = ctk.StringVar(value=s.get("output_mode", "image"))
        self.image_count = ctk.IntVar(value=3 if int(s.get("image_count", 3)) == 3 else 4)
        self.dir_vars = [ctk.StringVar(value=x) for x in dirs]
        self.pick_mode = ctk.StringVar(value=self._pick_label(s.get("pick_mode", "separate")))
        self.canvas_mode = ctk.StringVar(value=s.get("canvas_preset", "9:16"))
        self.custom_w = ctk.StringVar(value=str(s.get("custom_width", 1080)))
        self.custom_h = ctk.StringVar(value=str(s.get("custom_height", 1920)))
        self.ratios = [ctk.DoubleVar(value=v) for v in [33, 34, 33, 25]]
        self.seam_blur = ctk.BooleanVar(value=bool(s.get("seam_blur", True)))
        self.blur_width = ctk.DoubleVar(value=float(s.get("blur_width", 24)))
        self.blur_strength = ctk.DoubleVar(value=float(s.get("blur_strength", 6)))
        self.jpg_quality = ctk.StringVar(value=str(s.get("jpg_quality", 95)))
        self.min_duration = ctk.StringVar(value=str(s.get("video_min_duration", 3)))
        self.max_duration = ctk.StringVar(value=str(s.get("video_max_duration", 5)))
        self.transition_duration = ctk.StringVar(value=str(s.get("transition_duration", 0.6)))
        self.fps = ctk.StringVar(value=str(s.get("fps", 30)))
        self.crf = ctk.StringVar(value=str(s.get("video_crf", 20)))
        self.batch_count = ctk.StringVar(value=str(s.get("batch_count", 20)))
        self.prefix = ctk.StringVar(value=str(s.get("file_prefix", "游戏素材")))
        self.output_dir = ctk.StringVar(value=str(s.get("output_directory", "")))
        selected = set(s.get("transitions", list(SUPPORTED_TRANSITIONS)))
        self.transition_vars = {code: ctk.BooleanVar(value=code in selected) for code in SUPPORTED_TRANSITIONS}

    @staticmethod
    def _pick_label(code: str) -> str:
        for label, value in PICK.items():
            if value == code:
                return label
        return "每个目录各取1张"

    def _card(self, parent, title: str, subtitle: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
        ctk.CTkLabel(
            card, text=title, text_color=TEXT,
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 1))
        ctk.CTkLabel(
            card, text=subtitle, text_color=MUTED,
            font=ctk.CTkFont(size=10)
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 11))
        return card

    def _label(self, parent, text: str, row: int) -> None:
        ctk.CTkLabel(
            parent, text=text, text_color=MUTED,
            font=ctk.CTkFont(size=11)
        ).grid(row=row, column=0, sticky="w", padx=16, pady=6)

    def _button(self, parent, text: str, command, width: int = 72, primary: bool = False):
        if primary:
            return ctk.CTkButton(
                parent, text=text, command=command, width=width, height=38,
                corner_radius=9, fg_color=BLUE, hover_color=BLUE,
                font=ctk.CTkFont(size=12, weight="bold")
            )
        return ctk.CTkButton(
            parent, text=text, command=command, width=width, height=34,
            corner_radius=8, fg_color=ALT,
            hover_color=("#E8EDF4", "#2B333E"), text_color=TEXT,
            border_width=1, border_color=BORDER
        )

    def _build_ui(self) -> None:
        self.configure(fg_color=BG)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(
            self, fg_color=CARD, corner_radius=0,
            border_width=1, border_color=BORDER, height=76
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkFrame(header, width=44, height=44, corner_radius=13, fg_color=BLUE)
        logo.grid(row=0, column=0, padx=(22, 12), pady=16)
        logo.grid_propagate(False)
        ctk.CTkLabel(
            logo, text="▶", text_color="#FFFFFF",
            font=ctk.CTkFont(size=18, weight="bold")
        ).place(relx=.5, rely=.5, anchor="center")

        box = ctk.CTkFrame(header, fg_color="transparent")
        box.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            box, text="ImageToAnimation", text_color=TEXT,
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            box, text="游戏素材批量制作工具", text_color=MUTED,
            font=ctk.CTkFont(size=10)
        ).pack(anchor="w")

        self.mode_badge = ctk.CTkLabel(
            header, text="图片 · 3图", width=105, height=30,
            corner_radius=15, fg_color=("#EEF4FF", "#18233D"),
            text_color=BLUE, font=ctk.CTkFont(size=10, weight="bold")
        )
        self.mode_badge.grid(row=0, column=2, padx=8)

        self.header_ffmpeg = ctk.CTkLabel(
            header, text="FFmpeg 检测中…", text_color=MUTED,
            font=ctk.CTkFont(size=10)
        )
        self.header_ffmpeg.grid(row=0, column=3, padx=(6, 20))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, minsize=410)
        body.grid_rowconfigure(0, weight=1)

        self.left = ctk.CTkScrollableFrame(body, fg_color="transparent")
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.left.grid_columnconfigure(0, weight=1)

        self.right = ctk.CTkFrame(
            body, fg_color=CARD, corner_radius=16,
            border_width=1, border_color=BORDER
        )
        self.right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self._build_mode()
        self._build_dirs()
        self._build_canvas()
        self._build_ratios()
        self._build_image_settings()
        self._build_video_settings()
        self._build_batch()
        self._build_preview()

    def _build_mode(self) -> None:
        f = self._card(
            self.left, "输出模式",
            "同一套素材，可生成拼接图片或 FFmpeg 短视频。"
        )
        f.grid(row=0, column=0, sticky="ew", padx=2, pady=6)
        f.grid_columnconfigure(0, weight=1)
        self.mode_seg = ctk.CTkSegmentedButton(
            f, values=["拼接图片", "图片视频"], command=self._mode_changed,
            selected_color=BLUE, selected_hover_color=BLUE
        )
        self.mode_seg.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 9))
        self.count_seg = ctk.CTkSegmentedButton(
            f, values=["3 张", "4 张"], command=self._count_changed,
            selected_color=BLUE, selected_hover_color=BLUE
        )
        self.count_seg.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))

    def _build_dirs(self) -> None:
        f = self._card(
            self.left, "素材目录",
            "目录顺序对应图片顺序；3 图模式自动停用目录 4。"
        )
        f.grid(row=1, column=0, sticky="ew", padx=2, pady=6)
        f.grid_columnconfigure(1, weight=1)
        self.dir_entries, self.dir_buttons = [], []
        for i in range(4):
            ctk.CTkLabel(
                f, text=f"{i + 1:02d}", width=28, text_color=BLUE,
                font=ctk.CTkFont(size=11, weight="bold")
            ).grid(row=i + 2, column=0, padx=(16, 4), pady=5, sticky="w")
            e = ctk.CTkEntry(
                f, textvariable=self.dir_vars[i], height=35,
                fg_color=ALT, border_color=BORDER
            )
            e.grid(row=i + 2, column=1, sticky="ew", padx=6, pady=5)
            b = self._button(f, "选择", lambda n=i: self._choose_dir(n), 62)
            b.grid(row=i + 2, column=2, padx=(2, 16), pady=5)
            self.dir_entries.append(e)
            self.dir_buttons.append(b)

    def _build_canvas(self) -> None:
        f = self._card(
            self.left, "成品画布",
            "常用比例直接选择，也支持自定义尺寸。"
        )
        f.grid(row=2, column=0, sticky="ew", padx=2, pady=6)
        f.grid_columnconfigure(0, weight=1)
        self.canvas_seg = ctk.CTkSegmentedButton(
            f, values=["9:16", "3:4", "16:9", "自定义"],
            command=self._canvas_changed,
            selected_color=BLUE, selected_hover_color=BLUE
        )
        self.canvas_seg.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 10))

        self.custom = ctk.CTkFrame(f, fg_color="transparent")
        self.custom.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        ctk.CTkLabel(self.custom, text="宽", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            self.custom, width=88, height=33,
            textvariable=self.custom_w, fg_color=ALT, border_color=BORDER
        ).pack(side="left", padx=6)
        ctk.CTkLabel(self.custom, text="高", text_color=MUTED).pack(side="left")
        ctk.CTkEntry(
            self.custom, width=88, height=33,
            textvariable=self.custom_h, fg_color=ALT, border_color=BORDER
        ).pack(side="left", padx=6)
        self.custom.grid_remove()

    def _build_ratios(self) -> None:
        f = self._card(
            self.left, "拼接高度",
            "拖动滑块调整每张图片的高度比例。"
        )
        f.grid(row=3, column=0, sticky="ew", padx=2, pady=6)
        f.grid_columnconfigure(1, weight=1)
        self.ratio_widgets = []
        for i in range(4):
            l = ctk.CTkLabel(f, text=f"图片 {i + 1}", text_color=MUTED)
            l.grid(row=i + 2, column=0, sticky="w", padx=16, pady=5)
            s = ctk.CTkSlider(
                f, from_=5, to=90, variable=self.ratios[i],
                progress_color=BLUE, button_color=BLUE,
                button_hover_color=BLUE,
                command=lambda _v: self._ratio_labels()
            )
            s.grid(row=i + 2, column=1, sticky="ew", padx=6, pady=5)
            v = ctk.CTkLabel(
                f, text="0%", width=50, text_color=TEXT,
                font=ctk.CTkFont(size=11, weight="bold")
            )
            v.grid(row=i + 2, column=2, padx=(4, 16), pady=5)
            self.ratio_widgets.append((l, s, v))

    def _build_image_settings(self) -> None:
        self.image_frame = self._card(
            self.left, "图片参数", "JPG 拼接图与接缝过渡。"
        )
        self.image_frame.grid(row=4, column=0, sticky="ew", padx=2, pady=6)
        self.image_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(
            self.image_frame, text="开启接缝虚化", variable=self.seam_blur,
            progress_color=BLUE, button_color=BLUE,
            button_hover_color=BLUE
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=7)
        self._label(self.image_frame, "虚化范围", 3)
        ctk.CTkSlider(
            self.image_frame, from_=4, to=100,
            variable=self.blur_width, progress_color=BLUE,
            button_color=BLUE, button_hover_color=BLUE
        ).grid(row=3, column=1, sticky="ew", padx=7, pady=6)
        self._label(self.image_frame, "虚化强度", 4)
        ctk.CTkSlider(
            self.image_frame, from_=1, to=30,
            variable=self.blur_strength, progress_color=BLUE,
            button_color=BLUE, button_hover_color=BLUE
        ).grid(row=4, column=1, sticky="ew", padx=7, pady=6)
        self._label(self.image_frame, "JPG质量", 5)
        ctk.CTkEntry(
            self.image_frame, width=90, height=33,
            textvariable=self.jpg_quality, fg_color=ALT,
            border_color=BORDER
        ).grid(row=5, column=1, sticky="w", padx=7, pady=(4, 12))

    def _build_video_settings(self) -> None:
        self.video_frame = self._card(
            self.left, "视频参数 · FFmpeg",
            "每张随机停留 3～5 秒，并使用随机转场。"
        )
        self.video_frame.grid(row=5, column=0, sticky="ew", padx=2, pady=6)
        self.video_frame.grid_columnconfigure(1, weight=1)
        self._label(self.video_frame, "单张停留", 2)
        d = ctk.CTkFrame(self.video_frame, fg_color="transparent")
        d.grid(row=2, column=1, sticky="w", padx=7, pady=5)
        ctk.CTkEntry(
            d, width=72, height=33, textvariable=self.min_duration,
            fg_color=ALT, border_color=BORDER
        ).grid(row=0, column=0)
        ctk.CTkLabel(d, text=" ～ ").grid(row=0, column=1)
        ctk.CTkEntry(
            d, width=72, height=33, textvariable=self.max_duration,
            fg_color=ALT, border_color=BORDER
        ).grid(row=0, column=2)
        ctk.CTkLabel(d, text=" 秒").grid(row=0, column=3)
        self._label(self.video_frame, "转场时长", 3)
        ctk.CTkEntry(
            self.video_frame, width=90, height=33,
            textvariable=self.transition_duration,
            fg_color=ALT, border_color=BORDER
        ).grid(row=3, column=1, sticky="w", padx=7, pady=5)
        self._label(self.video_frame, "随机转场", 4)
        tf = ctk.CTkFrame(self.video_frame, fg_color="transparent")
        tf.grid(row=4, column=1, columnspan=2, sticky="w", padx=7, pady=4)
        for i, (name, code) in enumerate(TRANS.items()):
            ctk.CTkCheckBox(
                tf, text=name, variable=self.transition_vars[code],
                width=82, checkbox_width=18, checkbox_height=18,
                fg_color=BLUE, hover_color=BLUE
            ).grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 7), pady=3)
        self._label(self.video_frame, "FPS", 6)
        ctk.CTkEntry(
            self.video_frame, width=90, height=33,
            textvariable=self.fps, fg_color=ALT, border_color=BORDER
        ).grid(row=6, column=1, sticky="w", padx=7, pady=5)
        self._label(self.video_frame, "H.264 CRF", 7)
        ctk.CTkEntry(
            self.video_frame, width=90, height=33,
            textvariable=self.crf, fg_color=ALT, border_color=BORDER
        ).grid(row=7, column=1, sticky="w", padx=7, pady=(5, 10))
        self.ffmpeg_label = ctk.CTkLabel(
            self.video_frame, text="", text_color=MUTED,
            font=ctk.CTkFont(size=10)
        )
        self.ffmpeg_label.grid(row=8, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 12))

    def _build_batch(self) -> None:
        f = self._card(
            self.left, "批量输出",
            "设置数量和保存位置，任务会在后台执行。"
        )
        f.grid(row=6, column=0, sticky="ew", padx=2, pady=6)
        f.grid_columnconfigure(1, weight=1)
        self._label(f, "生成数量", 2)
        ctk.CTkEntry(
            f, width=86, height=33, textvariable=self.batch_count,
            fg_color=ALT, border_color=BORDER
        ).grid(row=2, column=1, sticky="w", padx=7, pady=5)
        self._label(f, "文件名前缀", 3)
        ctk.CTkEntry(
            f, height=33, textvariable=self.prefix,
            fg_color=ALT, border_color=BORDER
        ).grid(row=3, column=1, columnspan=2, sticky="ew", padx=7, pady=5)
        self._label(f, "输出目录", 4)
        ctk.CTkEntry(
            f, height=33, textvariable=self.output_dir,
            fg_color=ALT, border_color=BORDER
        ).grid(row=4, column=1, sticky="ew", padx=7, pady=5)
        self._button(f, "选择", self._choose_output, 62).grid(
            row=4, column=2, padx=(2, 16), pady=5
        )

        actions = ctk.CTkFrame(f, fg_color="transparent")
        actions.grid(row=5, column=0, columnspan=3, sticky="ew", padx=16, pady=(12, 10))
        actions.grid_columnconfigure(1, weight=1)
        self.preview_btn = self._button(actions, "随机预览", self._preview, 110)
        self.preview_btn.grid(row=0, column=0, padx=(0, 8))
        self.batch_btn = self._button(
            actions, "开始批量生成", self._start_batch, primary=True
        )
        self.batch_btn.grid(row=0, column=1, sticky="ew")

        self.progress = ctk.CTkProgressBar(
            f, height=10, corner_radius=5,
            progress_color=BLUE, fg_color=ALT
        )
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew", padx=16, pady=5)
        self.progress.set(0)
        self.progress_label = ctk.CTkLabel(
            f, text="等待开始", text_color=MUTED, anchor="w"
        )
        self.progress_label.grid(row=7, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 7))
        self.log = ctk.CTkTextbox(
            f, height=95, corner_radius=9, fg_color=ALT,
            border_width=1, border_color=BORDER, text_color=TEXT
        )
        self.log.grid(row=8, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 14))
        self.log.configure(state="disabled")

    def _build_preview(self) -> None:
        ctk.CTkLabel(
            self.right, text="实时预览", text_color=TEXT,
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=18, pady=(18, 2))
        ctk.CTkLabel(
            self.right, text="查看随机素材的最终构图。",
            text_color=MUTED, font=ctk.CTkFont(size=10)
        ).pack(anchor="w", padx=18, pady=(0, 10))
        box = ctk.CTkFrame(
            self.right, fg_color=("#EEF2F7", "#0B0E12"),
            corner_radius=14, border_width=1, border_color=BORDER
        )
        box.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self.preview = ctk.CTkLabel(
            box, text="请先选择素材目录\n然后点击“随机预览”",
            text_color=MUTED, justify="center",
            fg_color=("#E6EBF2", "#171B22"), corner_radius=10,
            width=350, height=620
        )
        self.preview.place(relx=.5, rely=.5, anchor="center")
        info = ctk.CTkFrame(
            self.right, fg_color=ALT, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        info.pack(fill="x", padx=18, pady=(0, 18))
        self.preview_info = ctk.CTkLabel(
            info, text="尚未生成预览", text_color=MUTED,
            justify="left", anchor="w", wraplength=350,
            font=ctk.CTkFont(size=10)
        )
        self.preview_info.pack(fill="x", padx=12, pady=10)

    def _restore(self) -> None:
        self.mode_seg.set("拼接图片" if self.output_mode.get() == "image" else "图片视频")
        self.count_seg.set("3 张" if self.image_count.get() == 3 else "4 张")
        self.canvas_seg.set("自定义" if self.canvas_mode.get() == "custom" else self.canvas_mode.get())
        vals = (
            self.saved.get("ratios_3", [33, 34, 33])
            if self.image_count.get() == 3
            else self.saved.get("ratios_4", [25, 25, 25, 25])
        )
        for i, v in enumerate(vals[:self.image_count.get()]):
            self.ratios[i].set(float(v))
        self._refresh()
        self._canvas_changed(self.canvas_seg.get())
        self._ratio_labels()
        p = find_ffmpeg()
        self.header_ffmpeg.configure(text="FFmpeg 已就绪" if p else "FFmpeg 未找到")
        self.ffmpeg_label.configure(
            text=str(p) if p else r"请运行 scripts\download_ffmpeg.ps1"
        )

    def _refresh(self) -> None:
        four = self.image_count.get() == 4
        state = "normal" if four else "disabled"
        self.dir_entries[3].configure(state=state)
        self.dir_buttons[3].configure(state=state)
        if four:
            self.ratio_widgets[3][0].grid()
            self.ratio_widgets[3][1].grid()
            self.ratio_widgets[3][2].grid()
        else:
            for w in self.ratio_widgets[3]:
                w.grid_remove()
        if self.output_mode.get() == "image":
            self.image_frame.grid()
            self.video_frame.grid_remove()
            self.batch_btn.configure(text="开始批量生成图片")
        else:
            self.image_frame.grid_remove()
            self.video_frame.grid()
            self.batch_btn.configure(text="开始批量生成视频")
        self.mode_badge.configure(
            text=f"{'图片' if self.output_mode.get() == 'image' else '视频'} · {self.image_count.get()}图"
        )

    def _mode_changed(self, value: str) -> None:
        self.output_mode.set("image" if value == "拼接图片" else "video")
        self._refresh()

    def _count_changed(self, value: str) -> None:
        count = 3 if value.startswith("3") else 4
        self.image_count.set(count)
        defaults = (
            self.saved.get("ratios_3", [33, 34, 33])
            if count == 3
            else self.saved.get("ratios_4", [25, 25, 25, 25])
        )
        for i, v in enumerate(defaults[:count]):
            self.ratios[i].set(float(v))
        if count == 3 and PICK.get(self.pick_mode.get()) == "dir4":
            self.pick_mode.set("每个目录各取1张")
        self._refresh()
        self._ratio_labels()
        self.preview.configure(image=None, text="已切换模式\n请重新预览")
        self.preview_info.configure(text="尚未生成预览")

    def _canvas_changed(self, value: str) -> None:
        self.canvas_mode.set("custom" if value == "自定义" else value)
        if value == "自定义":
            self.custom.grid()
        else:
            self.custom.grid_remove()

    def _choose_dir(self, index: int) -> None:
        p = filedialog.askdirectory(initialdir=self.dir_vars[index].get() or None)
        if p:
            self.dir_vars[index].set(p)

    def _choose_output(self) -> None:
        p = filedialog.askdirectory(initialdir=self.output_dir.get() or None)
        if p:
            self.output_dir.set(p)

    def _size(self) -> tuple[int, int]:
        if self.canvas_mode.get() in CANVAS:
            return CANVAS[self.canvas_mode.get()]
        try:
            return (
                max(100, int(float(self.custom_w.get()))),
                max(100, int(float(self.custom_h.get())))
            )
        except ValueError as exc:
            raise ValueError("自定义宽度和高度必须是数字。") from exc

    def _ratio_values(self) -> list[float]:
        return [self.ratios[i].get() for i in range(self.image_count.get())]

    def _ratio_labels(self) -> None:
        vals = self._ratio_values()
        total = sum(vals) or 1
        used = 0.0
        for i, v in enumerate(vals):
            p = round(100 - used, 1) if i == len(vals) - 1 else round(v / total * 100, 1)
            if i < len(vals) - 1:
                used += p
            self.ratio_widgets[i][2].configure(text=f"{p}%")

    def _selector(self) -> MediaSelector:
        return MediaSelector(
            [v.get().strip() for v in self.dir_vars],
            self.image_count.get(),
            PICK.get(self.pick_mode.get(), "separate")
        )

    def _transitions(self) -> list[str]:
        return [c for c in SUPPORTED_TRANSITIONS if self.transition_vars[c].get()]

    @staticmethod
    def _random_transitions(pool: list[str], count: int) -> list[str]:
        if not pool:
            raise ValueError("至少勾选一种视频转场。")
        need = count - 1
        if len(pool) >= need:
            return random.sample(pool, need)
        out, last = [], None
        for _ in range(need):
            choices = [x for x in pool if x != last] or pool
            last = random.choice(choices)
            out.append(last)
        return out

    @staticmethod
    def _durations(lo: float, hi: float, count: int) -> list[float]:
        if lo <= 0 or hi <= 0:
            raise ValueError("单张停留时间必须大于0。")
        if lo > hi:
            lo, hi = hi, lo
        return [round(random.uniform(lo, hi), 2) for _ in range(count)]

    def _preview(self) -> None:
        try:
            paths = self._selector().pick(use_shuffle=False)
            w, h = self._size()
            image = compose_collage(
                paths, w, h, self._ratio_values(),
                seam_blur=self.output_mode.get() == "image" and self.seam_blur.get(),
                blur_width=round(self.blur_width.get()),
                blur_strength=round(self.blur_strength.get())
            )
            scale = min(350 / image.width, 620 / image.height)
            size = (
                max(1, round(image.width * scale)),
                max(1, round(image.height * scale))
            )
            image = image.resize(size, Image.Resampling.LANCZOS)
            self.preview_image = ctk.CTkImage(
                light_image=image, dark_image=image, size=size
            )
            self.preview.configure(image=self.preview_image, text="")
            text = [
                f"{'拼接图片' if self.output_mode.get() == 'image' else '图片视频'} · {len(paths)}图 · {w}×{h}"
            ]
            text.extend(f"{i + 1}. {p.name}" for i, p in enumerate(paths))
            self.preview_info.configure(text="\n".join(text))
        except Exception as exc:
            messagebox.showerror("预览失败", str(exc))

    def _config(self) -> dict:
        out = self.output_dir.get().strip()
        if not out:
            raise ValueError("请选择输出目录。")
        selector = self._selector()
        selector.validate()
        w, h = self._size()
        total = max(1, int(self.batch_count.get()))
        quality = max(50, min(100, int(self.jpg_quality.get())))
        cfg = {
            "output_dir": Path(out),
            "total": total,
            "prefix": safe_name(self.prefix.get()),
            "dirs": [v.get().strip() for v in self.dir_vars],
            "pick": PICK.get(self.pick_mode.get(), "separate"),
            "count": self.image_count.get(),
            "mode": self.output_mode.get(),
            "width": w,
            "height": h,
            "ratios": self._ratio_values(),
            "blur": self.seam_blur.get(),
            "blur_width": round(self.blur_width.get()),
            "blur_strength": round(self.blur_strength.get()),
            "quality": quality,
        }
        cfg["output_dir"].mkdir(parents=True, exist_ok=True)
        if cfg["mode"] == "video":
            FFmpegRunner().require()
            lo, hi = float(self.min_duration.get()), float(self.max_duration.get())
            self._durations(lo, hi, cfg["count"])
            pool = self._transitions()
            if not pool:
                raise ValueError("至少勾选一种视频转场。")
            cfg.update(
                low=lo,
                high=hi,
                transition_duration=max(.1, float(self.transition_duration.get())),
                fps=max(1, min(60, int(self.fps.get()))),
                crf=max(14, min(32, int(self.crf.get()))),
                transition_pool=pool
            )
        return cfg

    def _start_batch(self) -> None:
        if self.running:
            return
        try:
            cfg = self._config()
        except Exception as exc:
            messagebox.showerror("参数错误", str(exc))
            return
        self._save()
        self.running = True
        self.mode_badge.configure(text="处理中…")
        self.batch_btn.configure(state="disabled")
        self.preview_btn.configure(state="disabled")
        self.progress.set(0)
        self.progress_label.configure(text="准备开始……")
        threading.Thread(target=self._worker, args=(cfg,), daemon=True).start()

    def _worker(self, cfg: dict) -> None:
        try:
            selector = MediaSelector(cfg["dirs"], cfg["count"], cfg["pick"])
            selector.reset()
            used: set[tuple[str, ...]] = set()
            runner = FFmpegRunner() if cfg["mode"] == "video" else None
            for i in range(1, cfg["total"] + 1):
                paths = self._unique(selector, used)
                number = f"{i:03d}"
                if cfg["mode"] == "image":
                    image = compose_collage(
                        paths, cfg["width"], cfg["height"], cfg["ratios"],
                        seam_blur=cfg["blur"],
                        blur_width=cfg["blur_width"],
                        blur_strength=cfg["blur_strength"]
                    )
                    out = cfg["output_dir"] / f"{cfg['prefix']}_图片_{number}.jpg"
                    save_jpeg(image, out, cfg["quality"])
                else:
                    durations = self._durations(cfg["low"], cfg["high"], cfg["count"])
                    transitions = self._random_transitions(
                        cfg["transition_pool"], cfg["count"]
                    )
                    out = cfg["output_dir"] / f"{cfg['prefix']}_视频_{number}.mp4"
                    runner.create_slideshow(
                        paths, out, cfg["width"], cfg["height"],
                        durations, transitions,
                        cfg["transition_duration"], cfg["fps"], cfg["crf"]
                    )
                self._log(f"[{i}/{cfg['total']}] 完成：{out.name}")
                self.after(
                    0,
                    lambda cur=i, tot=cfg["total"]: self._progress(cur, tot)
                )
            self.after(0, lambda: self._done(True, "全部生成完成。"))
        except Exception as exc:
            self._log(f"[ERROR] {exc}")
            self.after(0, lambda err=str(exc): self._done(False, err))

    @staticmethod
    def _unique(selector: MediaSelector, used: set[tuple[str, ...]]) -> list[Path]:
        for _ in range(300):
            paths = selector.pick(use_shuffle=True)
            key = tuple(str(p.resolve()).lower() for p in paths)
            if key not in used:
                used.add(key)
                return paths
        raise RuntimeError("当前不重复组合数量不足，请增加素材或减少生成数量。")

    def _progress(self, cur: int, total: int) -> None:
        self.progress.set(cur / total)
        self.progress_label.configure(
            text=f"正在生成 {cur}/{total}（{round(cur / total * 100)}%）"
        )

    def _log(self, text: str) -> None:
        def add() -> None:
            self.log.configure(state="normal")
            self.log.insert("end", text + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.after(0, add)

    def _done(self, ok: bool, text: str) -> None:
        self.running = False
        self.batch_btn.configure(state="normal")
        self.preview_btn.configure(state="normal")
        self._refresh()
        self.progress.set(1 if ok else self.progress.get())
        self.progress_label.configure(
            text=text if ok else f"生成失败：{text}"
        )
        (messagebox.showinfo if ok else messagebox.showerror)(
            "完成" if ok else "生成失败", text
        )

    def _save(self) -> None:
        save_settings({
            "output_mode": self.output_mode.get(),
            "image_count": self.image_count.get(),
            "directories": [v.get().strip() for v in self.dir_vars],
            "pick_mode": PICK.get(self.pick_mode.get(), "separate"),
            "canvas_preset": self.canvas_mode.get(),
            "custom_width": self.custom_w.get(),
            "custom_height": self.custom_h.get(),
            "ratios_3": [self.ratios[i].get() for i in range(3)],
            "ratios_4": [self.ratios[i].get() for i in range(4)],
            "seam_blur": self.seam_blur.get(),
            "blur_width": self.blur_width.get(),
            "blur_strength": self.blur_strength.get(),
            "jpg_quality": self.jpg_quality.get(),
            "video_min_duration": self.min_duration.get(),
            "video_max_duration": self.max_duration.get(),
            "transition_duration": self.transition_duration.get(),
            "transitions": self._transitions(),
            "fps": self.fps.get(),
            "video_crf": self.crf.get(),
            "batch_count": self.batch_count.get(),
            "file_prefix": self.prefix.get(),
            "output_directory": self.output_dir.get(),
        })

    def _close(self) -> None:
        try:
            self._save()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
