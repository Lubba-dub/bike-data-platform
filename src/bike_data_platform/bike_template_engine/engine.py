from __future__ import annotations

from collections import defaultdict
from typing import Any

from .dataset_mapper import build_engine_payload_from_bike
from .template_package import MODE_META


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _lerp_color(color_a: tuple[int, int, int], color_b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(color_a, color_b))


def _metric_to_palette_color(metric_mode: str, value: float | None) -> str:
    if value is None:
        return "#d9dde3"
    t = _clamp(float(value))
    if metric_mode == "price_score":
        low, mid, high = (255, 246, 239), (247, 179, 122), (153, 31, 23)
    elif metric_mode == "quality_score":
        low, mid, high = (238, 246, 255), (142, 183, 255), (21, 48, 138)
    else:
        low, mid, high = (239, 252, 248), (139, 224, 203), (13, 107, 102)
    color = _lerp_color(low, mid, t / 0.5) if t <= 0.5 else _lerp_color(mid, high, (t - 0.5) / 0.5)
    return "#{:02x}{:02x}{:02x}".format(*color)


def _normalize_mode_values(parts: list[dict[str, Any]], metric_mode: str) -> list[float | None]:
    values = [part.get("metrics", {}).get(metric_mode) for part in parts if part.get("metrics", {}).get(metric_mode) is not None]
    if not values:
        return [None] * len(parts)
    minimum = min(float(value) for value in values)
    maximum = max(float(value) for value in values)
    if abs(maximum - minimum) < 1e-9:
        return [0.72 if part.get("metrics", {}).get(metric_mode) is not None else None for part in parts]
    normalized: list[float | None] = []
    for part in parts:
        value = part.get("metrics", {}).get(metric_mode)
        if value is None:
            normalized.append(None)
            continue
        normalized.append((float(value) - minimum) / (maximum - minimum))
    return normalized


def build_render_state(bike_payload: dict[str, Any], template_packages: dict[str, dict], metric_mode: str) -> dict[str, Any]:
    template_type = bike_payload["templateType"]
    template_package = template_packages[template_type]
    parts = [dict(part) for part in bike_payload.get("parts", [])]
    normalized_values = _normalize_mode_values(parts, metric_mode)
    selected_parts = []
    for part, normalized in zip(parts, normalized_values):
        render_status = "mapped" if part.get("templateLabels") else "template_missing"
        part["render"] = {
            "status": render_status,
            "fillValue": normalized,
            "fillColor": _metric_to_palette_color(metric_mode, normalized),
            "strokeOpacity": round(0.35 + 0.6 * float(part.get("evidence", {}).get("confidence") or 0.0), 2),
        }
        selected_parts.append(part)
    mapped = [part for part in selected_parts if part.get("render", {}).get("status") == "mapped"]
    template_coverage = round(len(mapped) / max(1, len(selected_parts)), 2)
    return {
        "bike": bike_payload,
        "mode": metric_mode,
        "modeMeta": MODE_META[metric_mode],
        "template": {
            "type": template_type,
            "label": template_package["title"],
            "description": template_package["description"],
            "svgBase": template_package["svgBase"],
            "mapping": template_package["mapping"],
            "supportedParts": template_package["supportedParts"],
        },
        "parts": selected_parts,
        "summary": {
            **bike_payload.get("summary", {}),
            "templateCoverage": template_coverage,
            "mode": metric_mode,
            "mappedPartLabels": sorted({label for part in selected_parts for label in part.get("templateLabels", [])}),
            "missingPartLabels": [
                part_key for part_key in template_package["supportedParts"]
                if part_key not in {label for part in selected_parts for label in part.get("templateLabels", [])}
            ],
        },
    }


def build_bike_catalog(bikes_api: list[dict[str, Any]], template_packages: dict[str, dict]) -> dict[str, Any]:
    bike_payloads = [build_engine_payload_from_bike(bike) for bike in bikes_api if bike.get("parts")]
    bike_payloads.sort(key=lambda bike: (bike["brand"], bike["bikeName"]))
    bikes_by_id = {bike["bikeId"]: bike for bike in bike_payloads}
    bike_options = [
        {
            "bikeId": bike["bikeId"],
            "bikeName": bike["bikeName"],
            "brand": bike["brand"],
            "bikeType": bike["bikeType"],
            "templateType": bike["templateType"],
            "partsCount": bike["summary"].get("partsCount", 0),
        }
        for bike in bike_payloads
    ]
    default_bike_id = bike_options[0]["bikeId"] if bike_options else None
    return {
        "bikes": bike_payloads,
        "bikesById": bikes_by_id,
        "bikeOptions": bike_options,
        "defaultBikeId": default_bike_id,
        "templatePackages": template_packages,
    }


def build_template_matrix(bike_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    brands = sorted({bike["brand"] for bike in bike_payloads})
    parts = sorted({part["partKey"] for bike in bike_payloads for part in bike.get("parts", [])})
    modes_payload: dict[str, dict[str, dict[str, dict[str, float | int | None]]]] = {}
    for metric_mode in MODE_META:
        mode_accum: dict[str, dict[str, dict[str, float | int]]] = defaultdict(lambda: defaultdict(lambda: {"sum": 0.0, "count": 0}))
        for bike in bike_payloads:
            for part in bike.get("parts", []):
                value = part.get("metrics", {}).get(metric_mode)
                if value is None:
                    continue
                cell = mode_accum[bike["brand"]][part["partKey"]]
                cell["sum"] += float(value)
                cell["count"] += 1
        brand_payload = {}
        for brand in brands:
            part_payload = {}
            for part_key in parts:
                cell = mode_accum[brand][part_key]
                count = int(cell["count"])
                part_payload[part_key] = {
                    "avg": round(float(cell["sum"]) / count, 4) if count else None,
                    "count": count,
                }
            brand_payload[brand] = part_payload
        modes_payload[metric_mode] = brand_payload
    return {"brands": brands, "parts": parts, "modes": modes_payload}
