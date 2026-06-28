from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat


POSITIVE_QUERY_KEYWORDS = {
    "side": 4,
    "side view": 5,
    "road bike": 2,
    "mountain bike": 2,
    "gravel bike": 2,
    "city bike": 1,
}

POSITIVE_TEXT_KEYWORDS = {
    "drop handle": 1,
    "road bike": 1,
    "gravel bike": 1,
    "mountain bike": 1,
    "full bike": 2,
    "frame": 1,
    "wheel": 1,
}

NEGATIVE_TEXT_KEYWORDS = {
    "helmet": -2,
    "glove": -2,
    "bag": -1,
    "pedal": -1,
    "close-up": -3,
    "close up": -3,
    "detail": -2,
    "part": -2,
}


@dataclass
class PrefilterResult:
    score: int
    decision: str
    reasons: list[str]
    width: int
    height: int
    aspect_ratio: float
    edge_box_ratio_w: float
    edge_box_ratio_h: float
    edge_box_aspect: float
    edge_density: float


def _score_text(query: str | None, title: str | None, description: str | None) -> tuple[int, list[str]]:
    text = " ".join(filter(None, [query, title, description])).lower()
    score = 0
    reasons: list[str] = []

    for keyword, value in POSITIVE_QUERY_KEYWORDS.items():
        if query and keyword in query.lower():
            score += value
            reasons.append(f"query含 {keyword} (+{value})")

    for keyword, value in POSITIVE_TEXT_KEYWORDS.items():
        if keyword in text:
            score += value
            reasons.append(f"text含 {keyword} (+{value})")

    for keyword, value in NEGATIVE_TEXT_KEYWORDS.items():
        if keyword in text:
            score += value
            reasons.append(f"text含 {keyword} ({value})")

    return score, reasons


def _edge_features(image_path: Path) -> tuple[int, int, float, float, float, float]:
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        max_side = 512
        scale = min(max_side / max(width, height), 1.0)
        resized = image.resize((max(1, int(width * scale)), max(1, int(height * scale))))
        gray = ImageOps.grayscale(resized)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(edges)
        mean = stat.mean[0]
        stddev = stat.stddev[0] if stat.stddev else 0
        threshold = min(255, max(20, int(mean + stddev)))
        mask = edges.point(lambda p: 255 if p >= threshold else 0)
        bbox = mask.getbbox()
        if bbox is None:
            return width, height, 0.0, 0.0, 0.0, 0.0

        x0, y0, x1, y1 = bbox
        box_w = max(1, x1 - x0)
        box_h = max(1, y1 - y0)
        mask_pixels = mask.load()
        active = 0
        for y in range(mask.height):
            for x in range(mask.width):
                if mask_pixels[x, y] > 0:
                    active += 1
        total = max(1, mask.width * mask.height)
        edge_density = active / total
        return (
            width,
            height,
            box_w / mask.width,
            box_h / mask.height,
            box_w / box_h,
            edge_density,
        )


def score_side_view_candidate(row: dict) -> PrefilterResult:
    image_path = Path(row["absolute_image_path"])
    score = 0
    reasons: list[str] = []

    text_score, text_reasons = _score_text(
        row.get("query"),
        row.get("title"),
        row.get("description"),
    )
    score += text_score
    reasons.extend(text_reasons)

    width, height, edge_w_ratio, edge_h_ratio, edge_aspect, edge_density = _edge_features(image_path)
    aspect_ratio = width / max(1, height)

    if aspect_ratio >= 1.45:
        score += 3
        reasons.append("图片横向比例明显偏宽 (+3)")
    elif aspect_ratio >= 1.2:
        score += 2
        reasons.append("图片为横图 (+2)")
    elif aspect_ratio < 0.95:
        score -= 4
        reasons.append("图片接近竖图或竖图 (-4)")

    if min(width, height) >= 500:
        score += 1
        reasons.append("分辨率足够 (+1)")
    else:
        score -= 2
        reasons.append("分辨率偏低 (-2)")

    if edge_w_ratio >= 0.55:
        score += 2
        reasons.append("主体边缘横向覆盖较宽 (+2)")
    else:
        score -= 2
        reasons.append("主体边缘横向覆盖不足 (-2)")

    if 0.22 <= edge_h_ratio <= 0.75:
        score += 2
        reasons.append("主体边缘纵向高度合理 (+2)")
    elif edge_h_ratio > 0.9:
        score -= 2
        reasons.append("主体几乎占满垂直方向，疑似非侧视整车 (-2)")

    if edge_aspect >= 1.35:
        score += 3
        reasons.append("主体边缘框偏横向，接近整车侧视布局 (+3)")
    elif edge_aspect < 0.95:
        score -= 3
        reasons.append("主体边缘框偏竖向，疑似非整车侧视 (-3)")

    if edge_density < 0.015:
        score -= 2
        reasons.append("图像结构边缘过少 (-2)")
    elif edge_density <= 0.12:
        score += 1
        reasons.append("图像边缘密度适中 (+1)")
    else:
        score -= 1
        reasons.append("图像边缘过密，背景可能较乱 (-1)")

    if score >= 9:
        decision = "keep"
    elif score >= 5:
        decision = "review"
    else:
        decision = "drop"

    return PrefilterResult(
        score=score,
        decision=decision,
        reasons=reasons,
        width=width,
        height=height,
        aspect_ratio=round(aspect_ratio, 4),
        edge_box_ratio_w=round(edge_w_ratio, 4),
        edge_box_ratio_h=round(edge_h_ratio, 4),
        edge_box_aspect=round(edge_aspect, 4),
        edge_density=round(edge_density, 6),
    )
