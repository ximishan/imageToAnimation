from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


SUPPORTED_TRANSITIONS = (
    "fade",
    "slideleft",
    "slideright",
    "slideup",
    "slidedown",
    "dissolve",
)


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def find_ffmpeg() -> Path | None:
    local = application_root() / "bin" / "ffmpeg.exe"
    if local.exists():
        return local

    found = shutil.which("ffmpeg")
    if found:
        return Path(found)

    return None


def find_ffprobe() -> Path | None:
    local = application_root() / "bin" / "ffprobe.exe"
    if local.exists():
        return local

    found = shutil.which("ffprobe")
    if found:
        return Path(found)

    return None


def _creation_flags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


class FFmpegRunner:
    def __init__(self, ffmpeg_path: str | Path | None = None) -> None:
        self.ffmpeg = Path(ffmpeg_path) if ffmpeg_path else find_ffmpeg()

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg and self.ffmpeg.exists())

    def require(self) -> Path:
        if not self.available:
            raise RuntimeError(
                "没有找到 FFmpeg。请运行 scripts\\download_ffmpeg.ps1，"
                "或把 ffmpeg.exe 放到程序目录的 bin 文件夹。"
            )
        return self.ffmpeg  # type: ignore[return-value]

    def create_slideshow(
        self,
        images: Sequence[str | Path],
        output_path: str | Path,
        width: int,
        height: int,
        durations: Sequence[float],
        transitions: Sequence[str],
        transition_duration: float = 0.6,
        fps: int = 30,
        crf: int = 20,
    ) -> None:
        ffmpeg = self.require()

        count = len(images)
        if count not in (3, 4):
            raise ValueError("视频素材数量必须是 3 或 4 张。")
        if len(durations) != count:
            raise ValueError("每张图片都必须有对应显示时长。")
        if len(transitions) != count - 1:
            raise ValueError("转场数量必须等于图片数量减一。")

        transition_duration = max(0.1, float(transition_duration))
        durations = [max(transition_duration + 0.2, float(v)) for v in durations]

        for transition in transitions:
            if transition not in SUPPORTED_TRANSITIONS:
                raise ValueError(f"不支持的转场：{transition}")

        width = max(100, int(width))
        height = max(100, int(height))
        fps = max(1, min(60, int(fps)))
        crf = max(14, min(32, int(crf)))

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        cmd: list[str] = [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
        ]

        for image, duration in zip(images, durations):
            cmd.extend(
                [
                    "-loop",
                    "1",
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    str(Path(image)),
                ]
            )

        total_duration = sum(durations) - transition_duration * (count - 1)
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-t",
                f"{total_duration:.3f}",
                "-i",
                "anullsrc=r=44100:cl=stereo",
            ]
        )

        filters: list[str] = []
        for index in range(count):
            filters.append(
                f"[{index}:v]"
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"setsar=1,"
                f"fps={fps},"
                f"format=yuv420p"
                f"[v{index}]"
            )

        previous = "v0"
        for index in range(1, count):
            offset = sum(durations[:index]) - transition_duration * index
            output_label = f"x{index}"
            filters.append(
                f"[{previous}][v{index}]"
                f"xfade=transition={transitions[index - 1]}:"
                f"duration={transition_duration:.3f}:"
                f"offset={offset:.3f}"
                f"[{output_label}]"
            )
            previous = output_label

        audio_input_index = count
        cmd.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                f"[{previous}]",
                "-map",
                f"{audio_input_index}:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                str(crf),
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-t",
                f"{total_duration:.3f}",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )

        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=_creation_flags(),
        )

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"FFmpeg 生成失败：{detail}")
