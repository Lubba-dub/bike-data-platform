from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


def build_white_background_mask(
    image: Image.Image,
    white_threshold: int = 245,
    diff_threshold: int = 18,
) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    src = rgb.load()

    def is_background_pixel(x: int, y: int) -> bool:
        r, g, b = src[x, y]
        min_channel = min(r, g, b)
        max_channel = max(r, g, b)
        return min_channel >= white_threshold and (max_channel - min_channel) <= diff_threshold

    background = Image.new("L", rgb.size, 0)
    bg = background.load()
    queue: deque[tuple[int, int]] = deque()
    visited: set[tuple[int, int]] = set()

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        visited.add((x, y))
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        if not is_background_pixel(x, y):
            continue
        bg[x, y] = 255
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                queue.append((nx, ny))

    mask = Image.new("L", rgb.size, 0)
    dst = mask.load()
    for y in range(height):
        for x in range(width):
            if bg[x, y] == 0:
                dst[x, y] = 255
    return mask


def clean_mask(mask: Image.Image) -> Image.Image:
    # Close small gaps and remove isolated speckles.
    mask = mask.filter(ImageFilter.MaxFilter(5))
    mask = mask.filter(ImageFilter.MinFilter(5))
    mask = mask.filter(ImageFilter.MedianFilter(3))
    return mask


def keep_largest_component(mask: Image.Image, min_area: int = 512) -> Image.Image:
    binary = mask.convert("L")
    width, height = binary.size
    pixels = binary.load()
    visited = bytearray(width * height)

    def idx(x: int, y: int) -> int:
        return y * width + x

    best_component: list[tuple[int, int]] = []
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 0:
                continue
            pos = idx(x, y)
            if visited[pos]:
                continue
            queue: deque[tuple[int, int]] = deque([(x, y)])
            visited[pos] = 1
            component: list[tuple[int, int]] = []
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    npos = idx(nx, ny)
                    if visited[npos] or pixels[nx, ny] == 0:
                        continue
                    visited[npos] = 1
                    queue.append((nx, ny))
            if len(component) > len(best_component):
                best_component = component

    output = Image.new("L", binary.size, 0)
    if len(best_component) < min_area:
        return output
    out = output.load()
    for x, y in best_component:
        out[x, y] = 255
    return output.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))


def render_silhouette(
    original: Image.Image,
    mask: Image.Image,
    silhouette_color: tuple[int, int, int] = (0, 0, 0),
    background_color: tuple[int, int, int] = (255, 255, 255),
    crop: bool = False,
    crop_padding: int = 24,
) -> tuple[Image.Image, Image.Image]:
    mask = mask.convert("L")
    rgb = Image.new("RGB", original.size, background_color)
    silhouette = Image.new("RGB", original.size, silhouette_color)
    composite = Image.composite(silhouette, rgb, mask)

    rgba = Image.new("RGBA", original.size, silhouette_color + (0,))
    alpha_mask = ImageOps.grayscale(mask)
    rgba.putalpha(alpha_mask)

    if not crop:
        return composite, rgba

    bbox = mask.getbbox()
    if not bbox:
        return composite, rgba
    left = max(0, bbox[0] - crop_padding)
    top = max(0, bbox[1] - crop_padding)
    right = min(mask.width, bbox[2] + crop_padding)
    bottom = min(mask.height, bbox[3] + crop_padding)
    region = (left, top, right, bottom)
    return composite.crop(region), rgba.crop(region)


def generate_silhouette_from_file(
    input_path: Path,
    output_dir: Path,
    white_threshold: int = 245,
    diff_threshold: int = 18,
    min_area: int = 512,
    crop: bool = False,
) -> dict:
    image = Image.open(input_path).convert("RGB")
    raw_mask = build_white_background_mask(
        image,
        white_threshold=white_threshold,
        diff_threshold=diff_threshold,
    )
    cleaned_mask = clean_mask(raw_mask)
    main_mask = keep_largest_component(cleaned_mask, min_area=min_area)
    silhouette_rgb, silhouette_rgba = render_silhouette(image, main_mask, crop=crop)

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    mask_path = output_dir / f"{stem}_mask.png"
    silhouette_path = output_dir / f"{stem}_silhouette.png"
    rgba_path = output_dir / f"{stem}_silhouette_rgba.png"

    main_mask.save(mask_path)
    silhouette_rgb.save(silhouette_path)
    silhouette_rgba.save(rgba_path)

    return {
        "input_path": str(input_path),
        "mask_path": str(mask_path),
        "silhouette_path": str(silhouette_path),
        "silhouette_rgba_path": str(rgba_path),
        "size": list(image.size),
        "mask_bbox": list(main_mask.getbbox()) if main_mask.getbbox() else None,
        "foreground_pixels": int(sum(1 for value in main_mask.getdata() if value > 0)),
    }


def write_silhouette_manifest(rows: list[dict], output_path: Path) -> None:
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
