from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image, ImageFilter, ImageOps


def normalize_ratios(values: Sequence[float], count: int) -> list[float]:
    active = [max(1.0, float(v)) for v in values[:count]]
    total = sum(active)
    if total <= 0:
        return [1.0 / count] * count
    return [v / total for v in active]


def calculate_heights(total_height: int, ratios: Sequence[float]) -> list[int]:
    heights: list[int] = []
    used = 0

    for index, ratio in enumerate(ratios):
        if index == len(ratios) - 1:
            height = total_height - used
        else:
            height = round(total_height * ratio)
            used += height
        heights.append(max(1, height))

    delta = total_height - sum(heights)
    heights[-1] += delta
    return heights


def _open_rgb(path: str | Path) -> Image.Image:
    with Image.open(path) as source:
        source = ImageOps.exif_transpose(source)
        if source.mode != "RGB":
            source = source.convert("RGB")
        return source.copy()


def _fit(path: str | Path, size: tuple[int, int]) -> Image.Image:
    image = _open_rgb(path)
    return ImageOps.fit(
        image,
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


def apply_seam_blur(
    image: Image.Image,
    seams: Sequence[int],
    width: int,
    strength: int,
) -> Image.Image:
    if not seams or width <= 0 or strength <= 0:
        return image

    result = image.copy()
    width = max(2, int(width))
    strength = max(1, int(strength))
    extra = max(width, strength * 4)

    for seam in seams:
        y0 = max(0, int(seam - width / 2))
        y1 = min(result.height, int(seam + width / 2))
        if y1 <= y0:
            continue

        src_y0 = max(0, y0 - extra)
        src_y1 = min(result.height, y1 + extra)

        region = result.crop((0, src_y0, result.width, src_y1))
        region = region.filter(ImageFilter.GaussianBlur(radius=strength))

        center_y0 = y0 - src_y0
        center_y1 = center_y0 + (y1 - y0)
        strip = region.crop((0, center_y0, result.width, center_y1))
        result.paste(strip, (0, y0))

    return result


def compose_collage(
    paths: Sequence[str | Path],
    width: int,
    height: int,
    ratios: Sequence[float],
    seam_blur: bool = True,
    blur_width: int = 24,
    blur_strength: int = 6,
) -> Image.Image:
    if len(paths) not in (3, 4):
        raise ValueError("拼接图片数量必须是 3 或 4 张。")

    width = max(100, int(width))
    height = max(100, int(height))
    normalized = normalize_ratios(ratios, len(paths))
    heights = calculate_heights(height, normalized)

    canvas = Image.new("RGB", (width, height), "black")
    seams: list[int] = []
    y = 0

    for index, (path, block_height) in enumerate(zip(paths, heights)):
        fitted = _fit(path, (width, block_height))
        canvas.paste(fitted, (0, y))
        y += block_height
        if index < len(paths) - 1:
            seams.append(y)

    if seam_blur:
        canvas = apply_seam_blur(
            canvas,
            seams=seams,
            width=blur_width,
            strength=blur_strength,
        )

    return canvas


def save_jpeg(image: Image.Image, output_path: str | Path, quality: int = 95) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        output,
        format="JPEG",
        quality=max(50, min(100, int(quality))),
        optimize=True,
        subsampling=0,
    )
