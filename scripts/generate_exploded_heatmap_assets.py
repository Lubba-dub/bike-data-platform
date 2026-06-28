from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.visualization.exploded_heatmap import (
    PART_LABEL_ORDER,
    build_demo_recognition_result,
    generate_exploded_heatmap_assets,
    generate_template_heatmap_assets,
)

PART_FROM_API = {
    "tyre": "tire",
    "brake": "brake",
    "cassette": "freewhile",
    "wheel": "tire",
    "fork": "fork",
    "frame": "frame",
    "saddle": "saddle",
    "seatpost": "seatpost",
    "handlebar": "handlebar",
    "crankset": "chainwheel",
    "pedal": "pedal",
    "derailleur": "rearderailleur",
    "shifter": "shiftlever",
    "chain": "chainwheel",
}


def build_recognition_result_from_api(api_path: Path, bike_name: str | None, metric_mode: str) -> dict:
    bikes = json.loads(api_path.read_text(encoding="utf-8"))
    if not bikes:
        return build_demo_recognition_result(metric_mode=metric_mode)

    selected = None
    if bike_name:
        bike_name_lower = bike_name.lower()
        for bike in bikes:
            if str(bike.get("bike_name", "")).lower() == bike_name_lower:
                selected = bike
                break
    if selected is None:
        selected = max(bikes, key=lambda bike: len(bike.get("parts", [])))

    parts_by_label = {}
    for part in selected.get("parts", []):
        source_key = str(part.get("part_key", "")).lower()
        mapped = PART_FROM_API.get(source_key)
        if not mapped:
            continue
        current = parts_by_label.get(mapped)
        score = part.get(metric_mode)
        if current is None or (score or 0) > (current.get(metric_mode) or 0):
            parts_by_label[mapped] = {
                "label": mapped,
                "display_label": mapped,
                "confidence": 0.88,
                "component_name": part.get("component_name") or part.get("value"),
                "offers_count": part.get("offers_count"),
                "reviews_count": part.get("reviews_count"),
                "price_score": part.get("price_score"),
                "quality_score": part.get("quality_score"),
                "value_score": part.get("value_score"),
            }

    demo = build_demo_recognition_result(metric_mode=metric_mode)
    merged = {part["label"]: part for part in demo["parts"]}
    merged.update(parts_by_label)
    return {
        "bike_name": selected.get("bike_name") or demo["bike_name"],
        "brand": selected.get("brand") or demo["brand"],
        "metric_mode": metric_mode,
        "views": selected.get("views"),
        "parts": [merged[label] for label in PART_LABEL_ORDER],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="根据识别结果或网站 API 生成 exploded heatmap 的 SVG/PNG 资产")
    parser.add_argument("--input-json", type=Path, help="识别结果 JSON 输入")
    parser.add_argument("--from-api", type=Path, default=ROOT / "data" / "gold" / "exports" / "website_bikes_api.json")
    parser.add_argument("--bike-name", type=str, help="指定从 website_bikes_api 中选取的 bike_name")
    parser.add_argument("--metric-mode", type=str, default="price_score", choices=["price_score", "quality_score", "value_score"])
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "visualizations" / "exploded_heatmap_demo")
    parser.add_argument("--template-svg", type=Path, help="基于指定 SVG 模板额外生成模板热力图")
    args = parser.parse_args()

    if args.input_json and args.input_json.exists():
        recognition_result = json.loads(args.input_json.read_text(encoding="utf-8"))
    elif args.from_api.exists():
        recognition_result = build_recognition_result_from_api(args.from_api, args.bike_name, args.metric_mode)
    else:
        recognition_result = build_demo_recognition_result(metric_mode=args.metric_mode)

    result = {
        "exploded": generate_exploded_heatmap_assets(recognition_result, args.output_dir, metric_mode=args.metric_mode)
    }
    if args.template_svg and args.template_svg.exists():
        result["template"] = generate_template_heatmap_assets(
            recognition_result,
            args.template_svg,
            args.output_dir,
            metric_mode=args.metric_mode,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
