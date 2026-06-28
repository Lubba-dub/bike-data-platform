from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.collectors.image_sources import BikeIndexImageCollector, WikimediaCommonsImageCollector
from bike_data_platform.settings import get_settings


def _ext_from_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def _download_image(url: str, target_path: Path, user_agent: str) -> bool:
    try:
        response = requests.get(url, headers={"User-Agent": user_agent}, timeout=60)
        response.raise_for_status()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(response.content)
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="采集自行车图片并生成标注前候选集")
    parser.add_argument("--source", choices=["bike_index", "wikimedia", "all"], default="all")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    cache_dir = settings.bronze_dir / "http_cache" / "image_sources"
    image_root = settings.project_root / "data" / "raw" / "images"
    manifest_root = settings.project_root / "data" / "annotations" / "manifests"
    manifest_root.mkdir(parents=True, exist_ok=True)

    bike_index_queries = [
        "road bike side",
        "mountain bike side",
        "gravel bike side",
        "city bike side",
        "bicycle"
    ]
    wikimedia_queries = [
        "bicycle side view",
        "road bicycle side view",
        "mountain bike side view"
    ]

    rows = []
    if args.source in {"bike_index", "all"}:
        collector = BikeIndexImageCollector(
            base_url="https://bikeindex.org/api/v3",
            user_agent="bike-data-platform/1.0 (+academic project)",
            cache_dir=cache_dir / "bike_index",
            per_page=50,
            max_pages=4,
        )
        rows.extend(collector.collect(bike_index_queries))

    if args.source in {"wikimedia", "all"}:
        collector = WikimediaCommonsImageCollector(
            user_agent="bike-data-platform/1.0 (+academic project)",
            cache_dir=cache_dir / "wikimedia",
            limit_per_query=40,
        )
        rows.extend(collector.collect(wikimedia_queries))

    dedup = {}
    for row in rows:
        dedup[(row["source"], row["source_id"], row["image_url"])] = row
    rows = list(dedup.values())[: args.limit]

    downloaded = 0
    for row in rows:
        image_hash = hashlib.md5(row["image_url"].encode("utf-8")).hexdigest()[:16]
        ext = _ext_from_url(row["image_url"])
        relative_path = Path(row["source"]) / f"{image_hash}{ext}"
        absolute_path = image_root / relative_path
        row["relative_image_path"] = str(relative_path)
        row["absolute_image_path"] = str(absolute_path)
        row["downloaded"] = False
        if args.download:
            row["downloaded"] = _download_image(
                row["image_url"],
                absolute_path,
                user_agent="bike-data-platform/1.0 (+academic project)",
            )
            downloaded += int(row["downloaded"])

    json_path = manifest_root / "bike_image_candidates.json"
    csv_path = manifest_root / "bike_image_candidates.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    if rows:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    print(
        json.dumps(
            {
                "candidate_count": len(rows),
                "downloaded_count": downloaded,
                "json_manifest": str(json_path),
                "csv_manifest": str(csv_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
