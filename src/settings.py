from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULTS: dict[str, Any] = {
    "output_mode": "image",
    "image_count": 3,
    "directories": ["", "", "", ""],
    "pick_mode": "separate",
    "canvas_preset": "9:16",
    "custom_width": 1080,
    "custom_height": 1920,
    "ratios_3": [33, 34, 33],
    "ratios_4": [25, 25, 25, 25],
    "seam_blur": True,
    "blur_width": 24,
    "blur_strength": 6,
    "jpg_quality": 95,
    "video_min_duration": 3.0,
    "video_max_duration": 5.0,
    "transition_duration": 0.6,
    "transitions": ["fade", "slideleft", "slideright", "slideup", "slidedown", "dissolve"],
    "fps": 30,
    "video_crf": 20,
    "batch_count": 20,
    "file_prefix": "游戏素材",
    "output_directory": "",
}


def settings_path() -> Path:
    base = os.getenv("APPDATA")
    if base:
        root = Path(base) / "imageToAnimation"
    else:
        root = Path.home() / ".imageToAnimation"
    root.mkdir(parents=True, exist_ok=True)
    return root / "settings.json"


def load_settings() -> dict[str, Any]:
    result = dict(DEFAULTS)
    path = settings_path()
    if not path.exists():
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            result.update(data)
    except Exception:
        pass

    dirs = result.get("directories")
    if not isinstance(dirs, list):
        result["directories"] = ["", "", "", ""]
    else:
        result["directories"] = (dirs + ["", "", "", ""])[:4]

    return result


def save_settings(data: dict[str, Any]) -> None:
    path = settings_path()
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
