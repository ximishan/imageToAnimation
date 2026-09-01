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

PICK_LABELS = {
    "每个目录各取1张": "separate",
    "所有启用目录混合随机": "mix",
    "全部从目录1抽取": "dir1",
    "全部从目录2抽取": "dir2",
    "全部从目录3抽取": "dir3",
    "全部从目录4抽取": "dir4",
}
PICK_REVERSE = {v: k for k, v in PICK_LABELS.items()}
CANVAS = {"9:16": (1080, 1920), "3:4": (1080, 1440), "16:9": (1920, 1080)}
TRANSITIONS = {
    "淡化": "fade",
    "向左滑": "slideleft",
    "向右滑": "slideright",
    "向上滑": "slideup",
    "向下滑": "slidedown",
    "溶解": "dissolve",
}


def safe_name(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", text.strip()) or "游戏素材"


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.saved = load_settings()
        self.title(f"ImageToAnimation v{__version__}")
        self.geometry("1260x850")
        self.minsize(1060, 720)
        self.running = False
        self.preview_image: ctk.CTkImage | None = None
        self._vars()
        self._ui()
        self._restore()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _vars(self) -> None:
        s = self.saved
        dirs = (s.get("directories", []) + ["", "", "", ""])[:4]
        self.output_mode = ctk.StringVar(value=s.get("output_mode", "image"))
        self.image_count = ctk.IntVar(value=3 if int(s.get("image_count", 3)) == 3 else 4)
        self.dir_vars = [ctk.StringVar(value=x) for x in dirs]
        self.pick_mode = ctk.StringVar(value=PICK_REVERSE.get(s.get("pick_mode", "separate"), "每个目录各取1张"))
        self.canvas_mode = ctk.StringVar(value=s.get("canvas_preset", "9:16"))
        self.custom_w = ctk.StringVar(value=str(s.get("custom_width", 1080)))
        self.custom_h = ctk.StringVar(value=str(s.get("custom_height", 1920)))
        self.ratios = [ctk.DoubleVar(value=v) for v in [33, 34, 33, 25]]
        self.seam_blur = ctk.BooleanVar(value=bool(s.get("seam_blur", True)))
        self.blur_width = ctk.DoubleVar(value=float(s.get("blur_width", 24)))
        self.blur_strength = ctk.DoubleVar(value=float(s.get("blur_strength", 6)))
        self.jpg_quality = ctk.StringVar(value=str(s.get("jpg_quality", 95)))
        self.min_duration = ctk.StringVar(value=str(s.get("video_min_duration", 3.0)))
        self.max_duration = ctk.StringVar(value=str(s.get("video_max_duration", 5.0)))
        self.transition_duration = ctk.StringVar(value=str(s.get("transition_duration", 0.6)))
        self.fps = ctk.StringVar(value=str(s.get("fps", 30)))
        self.crf = ctk.StringVar(value=str(s.get("video_crf", 20)))
        selected = set(s.get("transitions", SUPPORTED_TRANSITIONS))
        self.transition_vars = {code: ctk.BooleanVar(value=code in selected) for code in SUPPORTED_TRANSITIONS}
        self.batch_count = ctk.StringVar(value=str(s.get("batch_count", 20)))
        self.prefix = ctk.StringVar(value=str(s.get("file_prefix", "游戏素材")))
        self.output_dir = ctk.StringVar(value=str(s.get("output_directory", "")))

    def _section(self, title: str, row: int) -> ctk.CTkFrame:
        f = ctk.CTkFrame(self.left)
        f.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(12, 8)
        )
        return f

    def _ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.left = ctk.CTkScrollableFrame(self, width=750)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(14, 8), pady=14)
        self.left.grid_columnconfigure(0, weight=1)
        self.right = ctk.CTkFrame(self, width=420)
        self.right.grid(row=0, column=1, sticky="ns", padx=(8, 14), pady=14)
        self.right.grid_propagate(False)

        f = self._section("① 输出模式", 0)
        ctk.CTkLabel(f, text="类型").grid(row=1, column=0, sticky="w", padx=14, pady=7)
        self.mode_seg = ctk.CTkSegmentedButton(f, values=["拼接图片", "图片视频"], command=self._mode_changed)
        self.mode_seg.grid(row=1, column=1, sticky="w", padx=8, pady=7)
        ctk.CTkLabel(f, text="图片数量").grid(row=2, column=0, sticky="w", padx=14, pady=(7, 14))
        self.count_seg = ctk.CTkSegmentedButton(f, values=["3张", "4张"], command=self._count_changed)
        self.count_seg.grid(row=2, column=1, sticky="w", padx=8, pady=(7, 14))

        f = self._section("② 素材目录", 1)
        self.dir_entries, self.dir_buttons = [], []
        for i in range(4):
            ctk.CTkLabel(f, text=f"目录{i+1}").grid(row=i+1, column=0, sticky="w", padx=14, pady=5)
            e = ctk.CTkEntry(f, textvariable=self.dir_vars[i])
            e.grid(row=i+1, column=1, sticky="ew", padx=8, pady=5)
            b = ctk.CTkButton(f, text="选择", width=70, command=lambda n=i: self._choose_dir(n))
            b.grid(row=i+1, column=2, padx=(4, 14), pady=5)
            self.dir_entries.append(e)
            self.dir_buttons.append(b)

        f = self._section("③ 素材抽取", 2)
        ctk.CTkLabel(f, text="模式").grid(row=1, column=0, sticky="w", padx=14, pady=10)
        self.pick_menu = ctk.CTkOptionMenu(f, values=list(PICK_LABELS), variable=self.pick_mode)
        self.pick_menu.grid(row=1, column=1, sticky="w", padx=8, pady=10)
        ctk.CTkLabel(f, text="批量生成采用洗牌轮播，尽量让目录中的素材均匀使用。",
                     text_color=("gray40", "gray70")).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 12)
        )

        f = self._section("④ 成品画布", 3)
        ctk.CTkLabel(f, text="比例").grid(row=1, column=0, sticky="w", padx=14, pady=8)
        self.canvas_seg = ctk.CTkSegmentedButton(f, values=["9:16", "3:4", "16:9", "自定义"], command=self._canvas_changed)
        self.canvas_seg.grid(row=1, column=1, columnspan=2, sticky="w", padx=8, pady=8)
        self.custom_frame = ctk.CTkFrame(f, fg_color="transparent")
        self.custom_frame.grid(row=2, column=1, columnspan=2, sticky="w", padx=8, pady=(0, 12))
        ctk.CTkLabel(self.custom_frame, text="宽").grid(row=0, column=0, padx=(0, 5))
        ctk.CTkEntry(self.custom_frame, width=90, textvariable=self.custom_w).grid(row=0, column=1, padx=(0, 12))
        ctk.CTkLabel(self.custom_frame, text="高").grid(row=0, column=2, padx=(0, 5))
        ctk.CTkEntry(self.custom_frame, width=90, textvariable=self.custom_h).grid(row=0, column=3)

        f = self._section("⑤ 拼接高度比例", 4)
        self.ratio_widgets = []
        for i in range(4):
            label = ctk.CTkLabel(f, text=f"图片{i+1}")
            label.grid(row=i+1, column=0, sticky="w", padx=14, pady=5)
            slider = ctk.CTkSlider(f, from_=5, to=90, variable=self.ratios[i], command=lambda _x: self._ratio_labels())
            slider.grid(row=i+1, column=1, sticky="ew", padx=8, pady=5)
            value = ctk.CTkLabel(f, text="0%", width=55)
            value.grid(row=i+1, column=2, padx=(4, 14), pady=5)
            self.ratio_widgets.append((label, slider, value))

        self.image_frame = self._section("⑥ 图片模式设置", 5)
        ctk.CTkSwitch(self.image_frame, text="拼接处虚化", variable=self.seam_blur).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=14, pady=8
        )
        ctk.CTkLabel(self.image_frame, text="虚化范围").grid(row=2, column=0, sticky="w", padx=14, pady=6)
        ctk.CTkSlider(self.image_frame, from_=4, to=100, variable=self.blur_width).grid(row=2, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(self.image_frame, text="虚化强度").grid(row=3, column=0, sticky="w", padx=14, pady=6)
        ctk.CTkSlider(self.image_frame, from_=1, to=30, variable=self.blur_strength).grid(row=3, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(self.image_frame, text="JPG质量").grid(row=4, column=0, sticky="w", padx=14, pady=(6, 12))
        ctk.CTkEntry(self.image_frame, width=100, textvariable=self.jpg_quality).grid(row=4, column=1, sticky="w", padx=8, pady=(6, 12))

        self.video_frame = self._section("⑥ 视频模式设置（FFmpeg）", 6)
        ctk.CTkLabel(self.video_frame, text="单张停留").grid(row=1, column=0, sticky="w", padx=14, pady=6)
        d = ctk.CTkFrame(self.video_frame, fg_color="transparent")
        d.grid(row=1, column=1, sticky="w", padx=8, pady=6)
        ctk.CTkEntry(d, width=72, textvariable=self.min_duration).grid(row=0, column=0)
        ctk.CTkLabel(d, text=" ～ ").grid(row=0, column=1)
        ctk.CTkEntry(d, width=72, textvariable=self.max_duration).grid(row=0, column=2)
        ctk.CTkLabel(d, text=" 秒").grid(row=0, column=3)
        ctk.CTkLabel(self.video_frame, text="转场时长").grid(row=2, column=0, sticky="w", padx=14, pady=6)
        ctk.CTkEntry(self.video_frame, width=100, textvariable=self.transition_duration).grid(row=2, column=1, sticky="w", padx=8, pady=6)

        ctk.CTkLabel(self.video_frame, text="随机转场").grid(row=3, column=0, sticky="nw", padx=14, pady=6)
        tf = ctk.CTkFrame(self.video_frame, fg_color="transparent")
        tf.grid(row=3, column=1, columnspan=2, sticky="w", padx=8, pady=6)
        for i, (label, code) in enumerate(TRANSITIONS.items()):
            ctk.CTkCheckBox(tf, text=label, variable=self.transition_vars[code], width=90).grid(
                row=i//3, column=i%3, sticky="w", padx=(0, 8), pady=3
            )
        ctk.CTkLabel(self.video_frame, text="FPS").grid(row=4, column=0, sticky="w", padx=14, pady=6)
        ctk.CTkEntry(self.video_frame, width=100, textvariable=self.fps).grid(row=4, column=1, sticky="w", padx=8, pady=6)
        ctk.CTkLabel(self.video_frame, text="H.264 CRF").grid(row=5, column=0, sticky="w", padx=14, pady=6)
        ctk.CTkEntry(self.video_frame, width=100, textvariable=self.crf).grid(row=5, column=1, sticky="w", padx=8, pady=6)
        self.ffmpeg_label = ctk.CTkLabel(self.video_frame, text="", text_color=("gray40", "gray70"))
        self.ffmpeg_label.grid(row=6, column=0, columnspan=3, sticky="w", padx=14, pady=(2, 12))

        f = self._section("⑦ 批量输出", 7)
        ctk.CTkLabel(f, text="生成数量").grid(row=1, column=0, sticky="w", padx=14, pady=5)
        ctk.CTkEntry(f, width=100, textvariable=self.batch_count).grid(row=1, column=1, sticky="w", padx=8, pady=5)
        ctk.CTkLabel(f, text="文件名前缀").grid(row=2, column=0, sticky="w", padx=14, pady=5)
        ctk.CTkEntry(f, textvariable=self.prefix).grid(row=2, column=1, sticky="ew", padx=8, pady=5)
        ctk.CTkLabel(f, text="输出目录").grid(row=3, column=0, sticky="w", padx=14, pady=5)
        ctk.CTkEntry(f, textvariable=self.output_dir).grid(row=3, column=1, sticky="ew", padx=8, pady=5)
        ctk.CTkButton(f, text="选择", width=70, command=self._choose_output).grid(row=3, column=2, padx=(4, 14), pady=5)
        buttons = ctk.CTkFrame(f, fg_color="transparent")
        buttons.grid(row=4, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 7))
        self.preview_btn = ctk.CTkButton(buttons, text="随机预览", width=110, command=self._preview)
        self.preview_btn.grid(row=0, column=0, padx=(0, 8))
        self.batch_btn = ctk.CTkButton(buttons, text="开始批量生成", width=130, command=self._start_batch)
        self.batch_btn.grid(row=0, column=1)
        self.progress = ctk.CTkProgressBar(f)
        self.progress.grid(row=5, column=0, columnspan=3, sticky="ew", padx=14, pady=5)
        self.progress.set(0)
        self.progress_label = ctk.CTkLabel(f, text="等待开始")
        self.progress_label.grid(row=6, column=0, columnspan=3, sticky="w", padx=14)
        self.log = ctk.CTkTextbox(f, height=120)
        self.log.grid(row=7, column=0, columnspan=3, sticky="ew", padx=14, pady=(5, 14))
        self.log.configure(state="disabled")

        ctk.CTkLabel(self.right, text="预览", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 8)
        )
        self.preview = ctk.CTkLabel(
            self.right, text="选择素材目录后点击“随机预览”",
            width=388, height=650, fg_color=("gray90", "gray15"), corner_radius=10
        )
        self.preview.pack(padx=16, pady=8)
        self.preview_info = ctk.CTkLabel(self.right, text="", justify="left", anchor="w", wraplength=385)
        self.preview_info.pack(fill="x", padx=16, pady=(4, 12))

    def _restore(self) -> None:
        self.mode_seg.set("拼接图片" if self.output_mode.get() == "image" else "图片视频")
        self.count_seg.set("3张" if self.image_count.get() == 3 else "4张")
        self.canvas_seg.set("自定义" if self.canvas_mode.get() == "custom" else self.canvas_mode.get())
        values = self.saved.get("ratios_3", [33, 34, 33]) if self.image_count.get() == 3 else self.saved.get("ratios_4", [25]*4)
        for i, value in enumerate(values[:self.image_count.get()]):
            self.ratios[i].set(float(value))
        self._refresh()
        self._canvas_changed(self.canvas_seg.get())
        self._ratio_labels()
        path = find_ffmpeg()
        self.ffmpeg_label.configure(text=f"FFmpeg：{path}" if path else "FFmpeg：未找到，请运行 scripts\\download_ffmpeg.ps1")

    def _refresh(self) -> None:
        state = "normal" if self.image_count.get() == 4 else "disabled"
        self.dir_entries[3].configure(state=state)
        self.dir_buttons[3].configure(state=state)
        for w in self.ratio_widgets[3]:
            w.grid() if self.image_count.get() == 4 else w.grid_remove()
        if self.output_mode.get() == "image":
            self.image_frame.grid()
            self.video_frame.grid_remove()
        else:
            self.image_frame.grid_remove()
            self.video_frame.grid()

    def _mode_changed(self, value: str) -> None:
        self.output_mode.set("image" if value == "拼接图片" else "video")
        self._refresh()

    def _count_changed(self, value: str) -> None:
        count = 3 if value.startswith("3") else 4
        self.image_count.set(count)
        defaults = self.saved.get("ratios_3", [33, 34, 33]) if count == 3 else self.saved.get("ratios_4", [25]*4)
        for i, v in enumerate(defaults[:count]):
            self.ratios[i].set(float(v))
        if count == 3 and PICK_LABELS.get(self.pick_mode.get()) == "dir4":
            self.pick_mode.set(PICK_REVERSE["separate"])
        self._refresh()
        self._ratio_labels()
        self.preview.configure(image=None, text="已切换模式，请重新预览")
        self.preview_info.configure(text="")

    def _canvas_changed(self, value: str) -> None:
        self.canvas_mode.set("custom" if value == "自定义" else value)
        self.custom_frame.grid() if value == "自定义" else self.custom_frame.grid_remove()

    def _choose_dir(self, index: int) -> None:
        path = filedialog.askdirectory(initialdir=self.dir_vars[index].get() or None)
        if path:
            self.dir_vars[index].set(path)

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(initialdir=self.output_dir.get() or None)
        if path:
            self.output_dir.set(path)

    def _size(self) -> tuple[int, int]:
        if self.canvas_mode.get() in CANVAS:
            return CANVAS[self.canvas_mode.get()]
        try:
            return max(100, int(float(self.custom_w.get()))), max(100, int(float(self.custom_h.get())))
        except ValueError as exc:
            raise ValueError("自定义宽度和高度必须是数字。") from exc

    def _ratio_values(self) -> list[float]:
        return [self.ratios[i].get() for i in range(self.image_count.get())]

    def _ratio_labels(self) -> None:
        values = self._ratio_values()
        total = sum(values) or 1
        used = 0.0
        for i, v in enumerate(values):
            p = round(100-used, 1) if i == len(values)-1 else round(v/total*100, 1)
            if i < len(values)-1:
                used += p
            self.ratio_widgets[i][2].configure(text=f"{p}%")

    def _selector(self) -> MediaSelector:
        return MediaSelector(
            [v.get().strip() for v in self.dir_vars],
            self.image_count.get(),
            PICK_LABELS.get(self.pick_mode.get(), "separate"),
        )

    def _transitions(self) -> list[str]:
        return [code for code in SUPPORTED_TRANSITIONS if self.transition_vars[code].get()]

    @staticmethod
    def _random_transitions(pool: list[str], count: int) -> list[str]:
        need = count - 1
        if not pool:
            raise ValueError("至少勾选一种视频转场。")
        if len(pool) >= need:
            return random.sample(pool, need)
        result, last = [], None
        for _ in range(need):
            choices = [x for x in pool if x != last] or pool
            last = random.choice(choices)
            result.append(last)
        return result

    @staticmethod
    def _durations(low: float, high: float, count: int) -> list[float]:
        if low <= 0 or high <= 0:
            raise ValueError("单张停留时间必须大于0。")
        if low > high:
            low, high = high, low
        return [round(random.uniform(low, high), 2) for _ in range(count)]

    def _preview(self) -> None:
        try:
            paths = self._selector().pick(use_shuffle=False)
            w, h = self._size()
            image = compose_collage(
                paths, w, h, self._ratio_values(),
                seam_blur=self.output_mode.get() == "image" and self.seam_blur.get(),
                blur_width=round(self.blur_width.get()),
                blur_strength=round(self.blur_strength.get()),
            )
            scale = min(388/image.width, 650/image.height)
            size = (max(1, round(image.width*scale)), max(1, round(image.height*scale)))
            image = image.resize(size, Image.Resampling.LANCZOS)
            self.preview_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
            self.preview.configure(image=self.preview_image, text="")
            text = [f"{'拼接图片' if self.output_mode.get() == 'image' else '图片视频'} · {len(paths)}张 · {w}×{h}"]
            text.extend(f"{i+1}. {p.name}" for i, p in enumerate(paths))
            if self.output_mode.get() == "video":
                text.append("这里只预览素材组合；实际 MP4 使用 FFmpeg 随机转场。")
            self.preview_info.configure(text="\n".join(text))
        except Exception as exc:
            messagebox.showerror("预览失败", str(exc))

    def _config(self) -> dict:
        out = self.output_dir.get().strip()
        if not out:
            raise ValueError("请选择输出目录。")
        out_path = Path(out)
        out_path.mkdir(parents=True, exist_ok=True)

        count = self.image_count.get()
        selector = self._selector()
        selector.validate()
        w, h = self._size()
        cfg = {
            "output_dir": out_path,
            "total": max(1, int(self.batch_count.get())),
            "prefix": safe_name(self.prefix.get()),
            "dirs": [v.get().strip() for v in self.dir_vars],
            "pick": PICK_LABELS.get(self.pick_mode.get(), "separate"),
            "count": count,
            "mode": self.output_mode.get(),
            "width": w,
            "height": h,
            "ratios": self._ratio_values(),
            "blur": self.seam_blur.get(),
            "blur_width": round(self.blur_width.get()),
            "blur_strength": round(self.blur_strength.get()),
            "quality": max(50, min(100, int(self.jpg_quality.get()))),
        }
        if cfg["mode"] == "video":
            FFmpegRunner().require()
            low, high = float(self.min_duration.get()), float(self.max_duration.get())
            self._durations(low, high, count)
            pool = self._transitions()
            if not pool:
                raise ValueError("至少勾选一种视频转场。")
            cfg.update({
                "low": low, "high": high,
                "transition_duration": max(.1, float(self.transition_duration.get())),
                "fps": max(1, min(60, int(self.fps.get()))),
                "crf": max(14, min(32, int(self.crf.get()))),
                "transition_pool": pool,
            })
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

            for i in range(1, cfg["total"]+1):
                paths = self._unique_pick(selector, used)
                num = f"{i:03d}"
                if cfg["mode"] == "image":
                    image = compose_collage(
                        paths, cfg["width"], cfg["height"], cfg["ratios"],
                        seam_blur=cfg["blur"], blur_width=cfg["blur_width"],
                        blur_strength=cfg["blur_strength"],
                    )
                    output = cfg["output_dir"] / f"{cfg['prefix']}_图片_{num}.jpg"
                    save_jpeg(image, output, cfg["quality"])
                    self._log(f"[{i}/{cfg['total']}] 图片完成：{output.name}")
                else:
                    durations = self._durations(cfg["low"], cfg["high"], cfg["count"])
                    transitions = self._random_transitions(cfg["transition_pool"], cfg["count"])
                    output = cfg["output_dir"] / f"{cfg['prefix']}_视频_{num}.mp4"
                    runner.create_slideshow(
                        paths, output, cfg["width"], cfg["height"], durations, transitions,
                        cfg["transition_duration"], cfg["fps"], cfg["crf"],
                    )
                    self._log(
                        f"[{i}/{cfg['total']}] 视频完成：{output.name} | "
                        f"时长 {'/'.join(f'{x:.1f}s' for x in durations)} | "
                        f"转场 {'/'.join(transitions)}"
                    )
                self.after(0, lambda x=i, t=cfg["total"]: self._progress(x, t))
            self.after(0, lambda: self._done(True, "全部生成完成。"))
        except Exception as exc:
            self._log(f"[ERROR] {exc}")
            self.after(0, lambda e=str(exc): self._done(False, e))

    @staticmethod
    def _unique_pick(selector: MediaSelector, used: set[tuple[str, ...]]) -> list[Path]:
        for _ in range(300):
            paths = selector.pick(use_shuffle=True)
            key = tuple(str(p.resolve()).lower() for p in paths)
            if key not in used:
                used.add(key)
                return paths
        raise RuntimeError("当前不重复组合数量不足，请增加素材或减少生成数量。")

    def _progress(self, current: int, total: int) -> None:
        self.progress.set(current/total)
        self.progress_label.configure(text=f"正在生成 {current}/{total}（{round(current/total*100)}%）")

    def _log(self, text: str) -> None:
        def add() -> None:
            self.log.configure(state="normal")
            self.log.insert("end", text.rstrip()+"\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.after(0, add)

    def _done(self, ok: bool, text: str) -> None:
        self.running = False
        self.batch_btn.configure(state="normal")
        self.preview_btn.configure(state="normal")
        if ok:
            self.progress.set(1)
            self.progress_label.configure(text=text)
            messagebox.showinfo("完成", text)
        else:
            self.progress_label.configure(text=f"生成失败：{text}")
            messagebox.showerror("生成失败", text)

    def _save(self) -> None:
        save_settings({
            "output_mode": self.output_mode.get(),
            "image_count": self.image_count.get(),
            "directories": [v.get().strip() for v in self.dir_vars],
            "pick_mode": PICK_LABELS.get(self.pick_mode.get(), "separate"),
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
