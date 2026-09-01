from __future__ import annotations

import random
from pathlib import Path
from typing import Iterable


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}


def list_images(directory: str | Path) -> list[Path]:
    path = Path(directory)
    if not path.is_dir():
        return []

    return sorted(
        [
            item
            for item in path.iterdir()
            if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
        ],
        key=lambda p: p.name.lower(),
    )


def _key(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except Exception:
        return str(path).lower()


class ShuffleBag:
    def __init__(self, source: Iterable[Path] = ()) -> None:
        self.source: list[Path] = list(source)
        self.remaining: list[Path] = []

    def set_source(self, source: Iterable[Path]) -> None:
        self.source = list(source)
        self.remaining = []

    def reset(self) -> None:
        self.remaining = []

    def _refill(self) -> None:
        self.remaining = self.source.copy()
        random.shuffle(self.remaining)

    def take(self, excluded: Iterable[Path] = ()) -> Path:
        if not self.source:
            raise ValueError("对应素材目录没有图片。")

        excluded_keys = {_key(p) for p in excluded}
        max_attempts = max(8, len(self.source) * 4)

        for _ in range(max_attempts):
            if not self.remaining:
                self._refill()

            candidate = self.remaining.pop(0)
            if _key(candidate) not in excluded_keys:
                return candidate

            self.remaining.append(candidate)

        raise ValueError("素材数量不足，无法保证同一条成品内部不重复。")


class MediaSelector:
    def __init__(self, directories: list[str], image_count: int, mode: str) -> None:
        self.directories = (directories + ["", "", "", ""])[:4]
        self.image_count = 3 if int(image_count) == 3 else 4
        self.mode = mode
        self.sources = [list_images(d) for d in self.directories]
        self.bags = {
            f"dir{i + 1}": ShuffleBag(self.sources[i])
            for i in range(4)
        }
        self.mix_bag = ShuffleBag(self._active_flat())

    def _active_sources(self) -> list[list[Path]]:
        return self.sources[: self.image_count]

    def _active_flat(self) -> list[Path]:
        result: list[Path] = []
        for source in self._active_sources():
            result.extend(source)
        return result

    def reset(self) -> None:
        for bag in self.bags.values():
            bag.reset()
        self.mix_bag.set_source(self._active_flat())

    def validate(self) -> None:
        if self.mode == "separate":
            for index, source in enumerate(self._active_sources()):
                if not source:
                    raise ValueError(f"目录{index + 1}没有可用图片。")
            return

        if self.mode == "mix":
            total = len(self._active_flat())
            if total < self.image_count:
                raise ValueError(
                    f"启用目录合计至少需要 {self.image_count} 张图片，目前只有 {total} 张。"
                )
            return

        if self.mode.startswith("dir"):
            try:
                index = int(self.mode[3:]) - 1
            except ValueError as exc:
                raise ValueError("未知的素材抽取模式。") from exc

            if not 0 <= index <= 3:
                raise ValueError("未知的素材抽取模式。")
            if index >= self.image_count:
                raise ValueError(f"当前 {self.image_count} 图模式不能使用目录{index + 1}。")

            count = len(self.sources[index])
            if count < self.image_count:
                raise ValueError(
                    f"目录{index + 1}至少需要 {self.image_count} 张图片，目前只有 {count} 张。"
                )
            return

        raise ValueError("未知的素材抽取模式。")

    def pick(self, use_shuffle: bool = True) -> list[Path]:
        self.validate()

        if not use_shuffle:
            return self._pick_random()

        if self.mode == "separate":
            return [
                self.bags[f"dir{i + 1}"].take()
                for i in range(self.image_count)
            ]

        if self.mode == "mix":
            result: list[Path] = []
            for _ in range(self.image_count):
                result.append(self.mix_bag.take(result))
            return result

        index = int(self.mode[3:]) - 1
        bag = self.bags[f"dir{index + 1}"]
        result: list[Path] = []
        for _ in range(self.image_count):
            result.append(bag.take(result))
        return result

    def _pick_random(self) -> list[Path]:
        if self.mode == "separate":
            return [
                random.choice(self.sources[i])
                for i in range(self.image_count)
            ]

        if self.mode == "mix":
            return random.sample(self._active_flat(), self.image_count)

        index = int(self.mode[3:]) - 1
        return random.sample(self.sources[index], self.image_count)
