from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

CANVAS_WIDTH = 1600
CANVAS_HEIGHT = 1000
BACKGROUND_COLOR = (243, 242, 240)
NEUTRAL_COLOR = (190, 190, 190)
TEXT_COLOR = (45, 45, 45)
EDGE_COLOR = (95, 95, 95)

PART_LABEL_ORDER = [
    "tire",
    "brake",
    "chainwheel",
    "seatpost",
    "shock",
    "rearderailleur",
    "frame",
    "saddle",
    "fork",
    "freewhile",
    "crank",
    "handlebar",
    "shiftlever",
    "pedal",
]

LABEL_ALIASES = {
    "tyre": "tire",
    "rear_derailleur": "rearderailleur",
    "freewheel": "freewhile",
    "shifter": "shiftlever",
}

PART_TITLE_MAP = {
    "tire": "Tire",
    "brake": "Brake",
    "chainwheel": "Chainwheel",
    "seatpost": "Seatpost",
    "shock": "Shock",
    "rearderailleur": "Rear Derailleur",
    "frame": "Frame",
    "saddle": "Saddle",
    "fork": "Fork",
    "freewhile": "Freewhile",
    "crank": "Crank",
    "handlebar": "Handlebar",
    "shiftlever": "Shift Lever",
    "pedal": "Pedal",
}

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", SVG_NS)
ET.register_namespace("inkscape", INKSCAPE_NS)

TEMPLATE_LABEL_MAP = {
    "frame": "frame",
    "fork": "fork",
    "saddle": "saddle",
    "seatpost": "seatpost",
    "seatpostclamp": "seatpost",
    "shockabsorber": "shock",
    "rearshockabsorber": "shock",
    "handlebar": "handlebar",
    "steamcap": "handlebar",
    "stemcap": "handlebar",
    "shiftlever": "shiftlever",
    "brakelever": "brake",
    "brake": "brake",
    "fronttire": "tire",
    "backtire": "tire",
    "frontrim": "tire",
    "backrim": "tire",
    "chainwheel": "chainwheel",
    "crank": "crank",
    "rearderailleur": "rearderailleur",
    "freewheel": "freewhile",
    "frontbrake": "brake",
    "padal": "pedal",
    "pedal": "pedal",
}


@dataclass(frozen=True)
class PartShape:
    part_label: str
    kind: str
    data: tuple[float, ...]
    fill: bool = True
    stroke_width: int = 6


def _normalize_label(label: str) -> str:
    value = (label or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    return LABEL_ALIASES.get(value, value)


def _normalize_svg_token(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _resolve_template_part_label(value: str | None) -> str | None:
    normalized = _normalize_svg_token(value)
    direct = TEMPLATE_LABEL_MAP.get(normalized)
    if direct:
        return direct
    for prefix, mapped in TEMPLATE_LABEL_MAP.items():
        if normalized.startswith(prefix):
            return mapped
    return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _lerp_color(color_a: tuple[int, int, int], color_b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(color_a, color_b))


def metric_to_color(value: float | None) -> tuple[int, int, int]:
    if value is None:
        return NEUTRAL_COLOR
    t = _clamp(float(value))
    if t <= 0.5:
        return _lerp_color((43, 131, 186), (255, 242, 153), t / 0.5)
    return _lerp_color((255, 242, 153), (165, 0, 38), (t - 0.5) / 0.5)


def _rgb_to_hex(color: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def _parse_style(style_text: str | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not style_text:
        return parsed
    for chunk in style_text.split(";"):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _serialize_style(style_map: dict[str, str]) -> str:
    return ";".join(f"{key}:{value}" for key, value in style_map.items())


def _svg_numeric(value: str | None, fallback: float) -> float:
    if not value:
        return fallback
    numeric = "".join(ch for ch in value if ch.isdigit() or ch in ".-")
    try:
        return float(numeric)
    except ValueError:
        return fallback


def _rotated_rect_points(cx: float, cy: float, width: float, height: float, angle_deg: float) -> list[tuple[float, float]]:
    radians = math.radians(angle_deg)
    dx = width / 2
    dy = height / 2
    base = [(-dx, -dy), (dx, -dy), (dx, dy), (-dx, dy)]
    points = []
    for x, y in base:
        rx = x * math.cos(radians) - y * math.sin(radians)
        ry = x * math.sin(radians) + y * math.cos(radians)
        points.append((cx + rx, cy + ry))
    return points


def _polygon_svg(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _ellipse_bbox(cx: float, cy: float, radius_x: float, radius_y: float) -> tuple[float, float, float, float]:
    return (cx - radius_x, cy - radius_y, cx + radius_x, cy + radius_y)


def _part_shapes() -> list[PartShape]:
    return [
        PartShape("tire", "circle", (260, 640, 185), fill=False, stroke_width=18),
        PartShape("tire", "circle", (960, 640, 185), fill=False, stroke_width=18),
        PartShape("frame", "polygon", tuple(sum([
            list(point)
            for point in [
                (470, 350),
                (845, 320),
                (955, 525),
                (720, 770),
                (425, 725),
                (360, 595),
                (470, 350),
            ]
        ], []))),
        PartShape("frame", "line", (410, 585, 580, 420), fill=False, stroke_width=16),
        PartShape("frame", "line", (425, 725, 960, 640), fill=False, stroke_width=16),
        PartShape("seatpost", "polygon", tuple(sum([list(point) for point in _rotated_rect_points(465, 255, 34, 155, -12)], []))),
        PartShape("saddle", "ellipse", (420, 155, 76, 23)),
        PartShape("chainwheel", "circle", (705, 705, 82), fill=False, stroke_width=16),
        PartShape("chainwheel", "circle", (705, 705, 28), fill=False, stroke_width=8),
        PartShape("crank", "line", (705, 705, 810, 735), fill=False, stroke_width=12),
        PartShape("crank", "line", (705, 705, 620, 770), fill=False, stroke_width=12),
        PartShape("pedal", "polygon", tuple(sum([list(point) for point in _rotated_rect_points(840, 748, 70, 24, 0)], []))),
        PartShape("pedal", "polygon", tuple(sum([list(point) for point in _rotated_rect_points(600, 790, 70, 24, 0)], []))),
        PartShape("freewhile", "circle", (355, 710, 46), fill=False, stroke_width=10),
        PartShape("rearderailleur", "polygon", tuple(sum([
            list(point)
            for point in [(300, 785), (360, 760), (385, 820), (325, 860), (280, 830)]
        ], []))),
        PartShape("handlebar", "polygon", tuple(sum([
            list(point)
            for point in [(1085, 190), (1165, 160), (1210, 225), (1120, 270), (1060, 240)]
        ], []))),
        PartShape("shiftlever", "polygon", tuple(sum([
            list(point)
            for point in [(1085, 275), (1125, 255), (1135, 305), (1090, 320)]
        ], []))),
        PartShape("shiftlever", "polygon", tuple(sum([
            list(point)
            for point in [(1170, 280), (1210, 265), (1225, 315), (1180, 330)]
        ], []))),
        PartShape("brake", "polygon", tuple(sum([
            list(point)
            for point in [(1015, 300), (1038, 355), (1068, 330), (1050, 285)]
        ], []))),
        PartShape("brake", "polygon", tuple(sum([
            list(point)
            for point in [(1160, 295), (1188, 345), (1215, 325), (1198, 282)]
        ], []))),
        PartShape("brake", "polygon", tuple(sum([
            list(point)
            for point in [(1265, 825), (1292, 875), (1320, 855), (1298, 812)]
        ], []))),
        PartShape("fork", "polygon", tuple(sum([
            list(point)
            for point in [(1330, 350), (1370, 332), (1405, 820), (1375, 870), (1335, 860), (1348, 735), (1325, 735)]
        ], []))),
        PartShape("tire", "line", (75, 640, 445, 640), fill=False, stroke_width=2),
        PartShape("tire", "line", (775, 640, 1145, 640), fill=False, stroke_width=2),
    ]


def _metric_value(part_payload: dict[str, Any], metric_mode: str) -> float | None:
    value = part_payload.get(metric_mode)
    if value is None:
        value = part_payload.get("metric_values", {}).get(metric_mode)
    if value is None:
        value = part_payload.get("normalized_value")
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value > 1.0:
        return value
    return _clamp(value)


def _normalize_metric_values(parts: list[dict[str, Any]], metric_mode: str) -> dict[str, float | None]:
    raw_values: dict[str, float | None] = {}
    positive_values = []
    for part in parts:
        label = _normalize_label(str(part.get("label", "")))
        value = _metric_value(part, metric_mode)
        raw_values[label] = value
        if value is not None:
            positive_values.append(value)

    if not positive_values:
        return {label: None for label in PART_LABEL_ORDER}

    min_value = min(positive_values)
    max_value = max(positive_values)
    if math.isclose(min_value, max_value):
        return {label: (0.75 if raw_values.get(label) is not None else None) for label in PART_LABEL_ORDER}

    normalized = {}
    for label in PART_LABEL_ORDER:
        value = raw_values.get(label)
        if value is None:
            normalized[label] = None
        else:
            normalized[label] = (value - min_value) / (max_value - min_value)
    return normalized


def build_demo_recognition_result(metric_mode: str = "price_score") -> dict[str, Any]:
    base_values = {
        "tire": {"price_score": 0.93, "quality_score": 0.88, "value_score": 0.52},
        "brake": {"price_score": 0.36, "quality_score": 0.82, "value_score": 0.77},
        "chainwheel": {"price_score": 0.58, "quality_score": 0.63, "value_score": 0.51},
        "seatpost": {"price_score": 0.26, "quality_score": 0.74, "value_score": 0.83},
        "rearderailleur": {"price_score": 0.67, "quality_score": 0.86, "value_score": 0.66},
        "frame": {"price_score": 0.71, "quality_score": 0.69, "value_score": 0.55},
        "saddle": {"price_score": 0.28, "quality_score": 0.72, "value_score": 0.80},
        "fork": {"price_score": 0.62, "quality_score": 0.70, "value_score": 0.60},
        "freewhile": {"price_score": 0.43, "quality_score": 0.61, "value_score": 0.68},
        "crank": {"price_score": 0.55, "quality_score": 0.64, "value_score": 0.59},
        "handlebar": {"price_score": 0.34, "quality_score": 0.67, "value_score": 0.74},
        "shiftlever": {"price_score": 0.41, "quality_score": 0.77, "value_score": 0.81},
        "pedal": {"price_score": 0.24, "quality_score": 0.58, "value_score": 0.86},
    }
    return {
        "bike_name": "Demo Canonical Side View",
        "brand": "demo",
        "metric_mode": metric_mode,
        "parts": [
            {
                "label": label,
                "display_label": label,
                "confidence": round(0.9 - index * 0.02, 2),
                **base_values[label],
                "component_name": PART_TITLE_MAP[label],
                "offers_count": 3 + index % 4,
                "reviews_count": 6 + index,
            }
            for index, label in enumerate(PART_LABEL_ORDER)
        ],
    }


def _build_part_summary(recognition_result: dict[str, Any], metric_mode: str) -> list[dict[str, Any]]:
    parts = recognition_result.get("parts", [])
    normalized_values = _normalize_metric_values(parts, metric_mode)
    by_label = {_normalize_label(str(part.get("label", ""))): part for part in parts}
    summary = []
    for label in PART_LABEL_ORDER:
        raw_part = by_label.get(label, {})
        norm_value = normalized_values.get(label)
        summary.append(
            {
                "label": label,
                "display_label": raw_part.get("display_label", label),
                "title": PART_TITLE_MAP[label],
                "confidence": raw_part.get("confidence"),
                "component_name": raw_part.get("component_name"),
                "offers_count": raw_part.get("offers_count"),
                "reviews_count": raw_part.get("reviews_count"),
                "price_score": raw_part.get("price_score"),
                "quality_score": raw_part.get("quality_score"),
                "value_score": raw_part.get("value_score"),
                "normalized_value": norm_value,
                "fill_color": metric_to_color(norm_value),
            }
        )
    return summary


def _template_mapped_labels(template_svg_path: Path) -> tuple[list[str], list[str]]:
    root = ET.parse(template_svg_path).getroot()
    raw_labels = []
    mapped_labels = set()
    for el in root.iter():
        raw = el.attrib.get(f"{{{INKSCAPE_NS}}}label") or el.attrib.get("id")
        if not raw:
            continue
        raw_labels.append(raw)
        part_label = _resolve_template_part_label(raw)
        if part_label:
            mapped_labels.add(part_label)
    return sorted(mapped_labels), raw_labels


def _render_template_svg(
    part_summary: list[dict[str, Any]],
    template_svg_path: Path,
    output_path: Path,
    title: str,
    metric_mode: str,
) -> dict[str, Any]:
    tree = ET.parse(template_svg_path)
    root = tree.getroot()
    color_map = {part["label"]: _rgb_to_hex(part["fill_color"]) for part in part_summary}
    target_tags = {
        f"{{{SVG_NS}}}path",
        f"{{{SVG_NS}}}ellipse",
        f"{{{SVG_NS}}}circle",
        f"{{{SVG_NS}}}polygon",
        f"{{{SVG_NS}}}rect",
        f"{{{SVG_NS}}}line",
    }
    mapped_labels = set()
    for el in root.iter():
        if el.tag not in target_tags:
            continue
        raw_label = el.attrib.get(f"{{{INKSCAPE_NS}}}label") or el.attrib.get("id")
        part_label = _resolve_template_part_label(raw_label)
        style = _parse_style(el.attrib.get("style"))
        if part_label:
            mapped_labels.add(part_label)
            fill_color = color_map.get(part_label, _rgb_to_hex(NEUTRAL_COLOR))
            style["fill"] = fill_color
            if el.tag.endswith("line"):
                style["stroke"] = fill_color
            else:
                style.setdefault("stroke-width", "0.969463")
        else:
            if "fill" in style:
                style["fill"] = "#d4d4d4"
            elif el.tag != f"{{{SVG_NS}}}line":
                style["fill"] = "#d4d4d4"
        el.set("style", _serialize_style(style))

    view_box = root.attrib.get("viewBox")
    if view_box:
        _, _, width_text, height_text = view_box.split()
        orig_width = float(width_text)
        orig_height = float(height_text)
    else:
        orig_width = _svg_numeric(root.attrib.get("width"), 1408.0)
        orig_height = _svg_numeric(root.attrib.get("height"), 768.0)
    extra_height = 220.0
    root.set("viewBox", f"0 0 {orig_width:.0f} {orig_height + extra_height:.0f}")
    root.set("width", str(int(orig_width)))
    root.set("height", str(int(orig_height + extra_height)))

    legend_group = ET.SubElement(root, f"{{{SVG_NS}}}g", {"id": "heatmap_legend"})
    ET.SubElement(
        legend_group,
        f"{{{SVG_NS}}}rect",
        {
            "x": "0",
            "y": str(int(orig_height)),
            "width": str(int(orig_width)),
            "height": str(int(extra_height)),
            "fill": _rgb_to_hex(BACKGROUND_COLOR),
        },
    )
    ET.SubElement(
        legend_group,
        f"{{{SVG_NS}}}text",
        {
            "x": "54",
            "y": str(int(orig_height + 54)),
            "font-size": "30",
            "font-family": "Arial",
            "fill": _rgb_to_hex(TEXT_COLOR),
            "font-weight": "700",
        },
    ).text = title
    ET.SubElement(
        legend_group,
        f"{{{SVG_NS}}}text",
        {
            "x": "54",
            "y": str(int(orig_height + 88)),
            "font-size": "18",
            "font-family": "Arial",
            "fill": _rgb_to_hex(TEXT_COLOR),
        },
    ).text = f"Template heatmap rendered from normalized {metric_mode.replace('_', ' ')} values."

    bar_x = 54
    bar_y = int(orig_height + 118)
    bar_w = int(orig_width - 420)
    bar_h = 28
    steps = 120
    for i in range(steps):
        color = _rgb_to_hex(metric_to_color(i / (steps - 1)))
        x = bar_x + (bar_w / steps) * i
        ET.SubElement(
            legend_group,
            f"{{{SVG_NS}}}rect",
            {
                "x": f"{x:.2f}",
                "y": str(bar_y),
                "width": f"{bar_w / steps + 1:.2f}",
                "height": str(bar_h),
                "fill": color,
            },
        )
    ET.SubElement(
        legend_group,
        f"{{{SVG_NS}}}rect",
        {
            "x": str(bar_x),
            "y": str(bar_y),
            "width": str(bar_w),
            "height": str(bar_h),
            "fill": "none",
            "stroke": _rgb_to_hex(EDGE_COLOR),
            "stroke-width": "1",
        },
    )
    ET.SubElement(
        legend_group,
        f"{{{SVG_NS}}}text",
        {"x": str(bar_x), "y": str(bar_y - 10), "font-size": "18", "font-family": "Arial", "fill": _rgb_to_hex(TEXT_COLOR)},
    ).text = "Low"
    ET.SubElement(
        legend_group,
        f"{{{SVG_NS}}}text",
        {"x": str(bar_x + bar_w // 2), "y": str(bar_y - 10), "font-size": "18", "font-family": "Arial", "fill": _rgb_to_hex(TEXT_COLOR), "text-anchor": "middle"},
    ).text = metric_mode.replace("_", " ").title()
    ET.SubElement(
        legend_group,
        f"{{{SVG_NS}}}text",
        {"x": str(bar_x + bar_w), "y": str(bar_y - 10), "font-size": "18", "font-family": "Arial", "fill": _rgb_to_hex(TEXT_COLOR), "text-anchor": "end"},
    ).text = "High"

    legend_x = int(orig_width - 300)
    legend_y = int(orig_height + 32)
    for index, part in enumerate(part_summary):
        y = legend_y + index * 12
        ET.SubElement(
            legend_group,
            f"{{{SVG_NS}}}circle",
            {"cx": str(legend_x), "cy": str(y), "r": "4.5", "fill": _rgb_to_hex(part["fill_color"]), "stroke": _rgb_to_hex(EDGE_COLOR), "stroke-width": "0.8"},
        )
        ET.SubElement(
            legend_group,
            f"{{{SVG_NS}}}text",
            {"x": str(legend_x + 12), "y": str(y + 4), "font-size": "11", "font-family": "Arial", "fill": _rgb_to_hex(TEXT_COLOR)},
        ).text = f'{part["display_label"]}: {"N/A" if part["normalized_value"] is None else f"{part["normalized_value"]:.2f}"}'

    output_path.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
    return {
        "mapped_part_labels": sorted(mapped_labels),
        "missing_part_labels": [part["label"] for part in part_summary if part["label"] not in mapped_labels],
    }


def _render_svg(part_summary: list[dict[str, Any]], output_path: Path, title: str, metric_mode: str) -> None:
    color_map = {part["label"]: part["fill_color"] for part in part_summary}
    metric_display = metric_mode.replace("_", " ").title()
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}">',
        f'<rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="rgb{BACKGROUND_COLOR}" />',
        f'<text x="70" y="70" font-size="34" font-family="Arial" fill="rgb{TEXT_COLOR}" font-weight="700">{title}</text>',
        f'<text x="70" y="105" font-size="18" font-family="Arial" fill="rgb{TEXT_COLOR}">Exploded heatmap rendered from normalized {metric_display} values.</text>',
    ]
    for shape in _part_shapes():
        color = color_map.get(shape.part_label, NEUTRAL_COLOR)
        fill = f"rgb{color}" if shape.fill else "none"
        stroke = f"rgb{color}" if shape.fill or shape.kind == "circle" else f"rgb{EDGE_COLOR}"
        opacity = 0.96 if shape.fill else 0.9
        if shape.kind == "circle":
            cx, cy, radius = shape.data
            lines.append(
                f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{shape.stroke_width}" opacity="{opacity}"/>'
            )
        elif shape.kind == "ellipse":
            cx, cy, rx, ry = shape.data
            lines.append(
                f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="rgb{EDGE_COLOR}" stroke-width="2" opacity="{opacity}"/>'
            )
        elif shape.kind == "polygon":
            points = list(zip(shape.data[0::2], shape.data[1::2]))
            lines.append(
                f'<polygon points="{_polygon_svg(points)}" fill="{fill}" stroke="rgb{EDGE_COLOR}" stroke-width="2" opacity="{opacity}" />'
            )
        elif shape.kind == "line":
            x1, y1, x2, y2 = shape.data
            lines.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{shape.stroke_width}" stroke-linecap="round" opacity="{opacity}"/>'
            )

    legend_x = 1190
    legend_y = 140
    lines.append(f'<rect x="{legend_x}" y="{legend_y}" width="330" height="620" rx="24" fill="white" opacity="0.85" stroke="rgb{EDGE_COLOR}" stroke-width="1"/>')
    lines.append(f'<text x="{legend_x + 24}" y="{legend_y + 38}" font-size="24" font-family="Arial" fill="rgb{TEXT_COLOR}" font-weight="700">Part Metrics</text>')
    for index, part in enumerate(part_summary):
        y = legend_y + 76 + index * 40
        color = part["fill_color"]
        lines.append(f'<circle cx="{legend_x + 22}" cy="{y - 6}" r="11" fill="rgb{color}" stroke="rgb{EDGE_COLOR}" stroke-width="1"/>')
        score_text = "N/A" if part["normalized_value"] is None else f'{part["normalized_value"]:.2f}'
        lines.append(f'<text x="{legend_x + 45}" y="{y}" font-size="18" font-family="Arial" fill="rgb{TEXT_COLOR}">{part["display_label"]}</text>')
        lines.append(f'<text x="{legend_x + 255}" y="{y}" font-size="16" font-family="Arial" fill="rgb{TEXT_COLOR}" text-anchor="end">{score_text}</text>')

    bar_x, bar_y, bar_w, bar_h = 360, 900, 900, 32
    steps = 100
    for i in range(steps):
        t0 = i / (steps - 1)
        color = metric_to_color(t0)
        x = bar_x + (bar_w / steps) * i
        lines.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{bar_w/steps + 1:.2f}" height="{bar_h}" fill="rgb{color}" stroke="none"/>')
    lines.append(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" fill="none" stroke="rgb{EDGE_COLOR}" stroke-width="1"/>')
    lines.append(f'<text x="{bar_x}" y="{bar_y - 12}" font-size="18" font-family="Arial" fill="rgb{TEXT_COLOR}">Low</text>')
    lines.append(f'<text x="{bar_x + bar_w / 2}" y="{bar_y - 12}" font-size="20" font-family="Arial" fill="rgb{TEXT_COLOR}" text-anchor="middle">{metric_display} Heatmap</text>')
    lines.append(f'<text x="{bar_x + bar_w}" y="{bar_y - 12}" font-size="18" font-family="Arial" fill="rgb{TEXT_COLOR}" text-anchor="end">High</text>')
    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _draw_png(part_summary: list[dict[str, Any]], output_path: Path, title: str, metric_mode: str) -> None:
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    font_title = ImageFont.load_default()
    font_body = ImageFont.load_default()

    draw.text((70, 52), title, fill=TEXT_COLOR, font=font_title)
    draw.text((70, 86), f"Exploded heatmap rendered from normalized {metric_mode.replace('_', ' ')} values.", fill=TEXT_COLOR, font=font_body)
    color_map = {part["label"]: part["fill_color"] for part in part_summary}
    for shape in _part_shapes():
        color = color_map.get(shape.part_label, NEUTRAL_COLOR)
        if shape.kind == "circle":
            cx, cy, radius = shape.data
            bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
            if shape.fill:
                draw.ellipse(bbox, fill=color, outline=EDGE_COLOR, width=max(1, shape.stroke_width // 4))
            else:
                draw.ellipse(bbox, outline=color, width=shape.stroke_width)
        elif shape.kind == "ellipse":
            bbox = _ellipse_bbox(*shape.data)
            draw.ellipse(bbox, fill=color, outline=EDGE_COLOR, width=2)
        elif shape.kind == "polygon":
            points = list(zip(shape.data[0::2], shape.data[1::2]))
            draw.polygon(points, fill=color, outline=EDGE_COLOR)
        elif shape.kind == "line":
            draw.line(shape.data, fill=color if shape.part_label == "tire" else EDGE_COLOR, width=shape.stroke_width)

    legend_x, legend_y = 1190, 140
    draw.rounded_rectangle((legend_x, legend_y, legend_x + 330, legend_y + 620), radius=24, fill=(255, 255, 255), outline=EDGE_COLOR, width=1)
    draw.text((legend_x + 24, legend_y + 18), "Part Metrics", fill=TEXT_COLOR, font=font_title)
    for index, part in enumerate(part_summary):
        y = legend_y + 72 + index * 40
        color = part["fill_color"]
        draw.ellipse((legend_x + 10, y - 14, legend_x + 32, y + 8), fill=color, outline=EDGE_COLOR, width=1)
        score_text = "N/A" if part["normalized_value"] is None else f'{part["normalized_value"]:.2f}'
        draw.text((legend_x + 45, y - 10), str(part["display_label"]), fill=TEXT_COLOR, font=font_body)
        draw.text((legend_x + 255, y - 10), score_text, fill=TEXT_COLOR, font=font_body)

    bar_x, bar_y, bar_w, bar_h = 360, 900, 900, 32
    for i in range(bar_w):
        t = i / max(1, bar_w - 1)
        draw.line((bar_x + i, bar_y, bar_x + i, bar_y + bar_h), fill=metric_to_color(t), width=1)
    draw.rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), outline=EDGE_COLOR, width=1)
    draw.text((bar_x, bar_y - 22), "Low", fill=TEXT_COLOR, font=font_body)
    draw.text((bar_x + bar_w // 2 - 70, bar_y - 22), f"{metric_mode.replace('_', ' ').title()} Heatmap", fill=TEXT_COLOR, font=font_body)
    draw.text((bar_x + bar_w - 26, bar_y - 22), "High", fill=TEXT_COLOR, font=font_body)
    image.save(output_path)


def generate_exploded_heatmap_assets(
    recognition_result: dict[str, Any],
    output_dir: Path,
    metric_mode: str | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    effective_metric = metric_mode or recognition_result.get("metric_mode") or "price_score"
    summary = _build_part_summary(recognition_result, effective_metric)
    title = f'{recognition_result.get("brand", "demo")} {recognition_result.get("bike_name", "bike")} Exploded Heatmap'

    payload_path = output_dir / "exploded_heatmap_payload.json"
    svg_path = output_dir / "exploded_heatmap.svg"
    png_path = output_dir / "exploded_heatmap.png"

    payload = {
        "bike_name": recognition_result.get("bike_name"),
        "brand": recognition_result.get("brand"),
        "metric_mode": effective_metric,
        "parts": [
            {
                **part,
                "fill_color": "#{:02x}{:02x}{:02x}".format(*part["fill_color"]),
            }
            for part in summary
        ],
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _render_svg(summary, svg_path, title, effective_metric)
    _draw_png(summary, png_path, title, effective_metric)
    return {
        "payload_path": str(payload_path),
        "svg_path": str(svg_path),
        "png_path": str(png_path),
    }


def generate_template_heatmap_assets(
    recognition_result: dict[str, Any],
    template_svg_path: Path,
    output_dir: Path,
    metric_mode: str | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    effective_metric = metric_mode or recognition_result.get("metric_mode") or "price_score"
    summary = _build_part_summary(recognition_result, effective_metric)
    title = f'{recognition_result.get("brand", "demo")} {recognition_result.get("bike_name", "bike")} Template Heatmap'
    payload_path = output_dir / "template_heatmap_payload.json"
    svg_path = output_dir / "template_heatmap.svg"
    template_meta = _render_template_svg(summary, template_svg_path, svg_path, title, effective_metric)
    payload = {
        "bike_name": recognition_result.get("bike_name"),
        "brand": recognition_result.get("brand"),
        "metric_mode": effective_metric,
        "template_svg_path": str(template_svg_path),
        "mapped_part_labels": template_meta["mapped_part_labels"],
        "missing_part_labels": template_meta["missing_part_labels"],
        "parts": [
            {
                **part,
                "fill_color": _rgb_to_hex(part["fill_color"]),
            }
            for part in summary
        ],
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "payload_path": str(payload_path),
        "svg_path": str(svg_path),
    }
