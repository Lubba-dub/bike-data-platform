from __future__ import annotations

import json
import sys
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.collectors.api_bike_index import BikeIndexCollector
from bike_data_platform.collectors.static_pages import BikeComponentsCollector, BikeRadarCollector
from bike_data_platform.settings import get_settings
from bike_data_platform.storage import write_jsonl


def main() -> None:
    settings = get_settings()
    cfg = settings.config["collectors"]
    run_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    results = []
    errors = []

    cache_dir = settings.bronze_dir / "http_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    bike_index_cfg = cfg["bike_index"]
    if bike_index_cfg.get("enabled"):
        collector = BikeIndexCollector(
            base_url=bike_index_cfg["base_url"],
            user_agent=bike_index_cfg["user_agent"],
            cache_dir=cache_dir / "bike_index",
            per_page=int(bike_index_cfg.get("per_page", 25)),
            max_pages=int(bike_index_cfg.get("max_pages", 3)),
        )
        manufacturer_rows = collector.fetch_manufacturers()
        manufacturer_path = settings.raw_crawl_dir / f"{run_at}_bike_index_manufacturers.jsonl"
        write_jsonl(manufacturer_path, manufacturer_rows)
        results.append({"source": "bike_index_manufacturers", "count": len(manufacturer_rows), "path": str(manufacturer_path)})

        try:
            bike_rows = []
            for query in bike_index_cfg.get("search_queries", []):
                bike_rows.extend(collector.search_bikes(query))
            bike_path = settings.raw_crawl_dir / f"{run_at}_bike_index_bikes.jsonl"
            write_jsonl(bike_path, bike_rows)
            results.append({"source": "bike_index_bikes", "count": len(bike_rows), "path": str(bike_path)})
        except Exception as exc:
            errors.append({"source": "bike_index_bikes", "error": str(exc)})

    bike_components_cfg = cfg["bike_components"]
    if bike_components_cfg.get("enabled"):
        collector = BikeComponentsCollector(
            user_agent=bike_components_cfg["user_agent"],
            cache_dir=cache_dir / "bike_components",
        )
        rows = []
        for url in bike_components_cfg.get("start_urls", []):
            try:
                rows.extend(collector.fetch(url))
            except Exception as exc:
                errors.append({"source": "bike_components", "url": url, "error": str(exc)})
        path = settings.raw_crawl_dir / f"{run_at}_bike_components.jsonl"
        write_jsonl(path, rows)
        results.append({"source": "bike_components", "count": len(rows), "path": str(path)})

    bikeradar_cfg = cfg["bikeradar"]
    if bikeradar_cfg.get("enabled"):
        collector = BikeRadarCollector(
            user_agent=bikeradar_cfg["user_agent"],
            cache_dir=cache_dir / "bikeradar",
        )
        rows = []
        for url in bikeradar_cfg.get("start_urls", []):
            try:
                rows.extend(collector.fetch(url))
            except Exception as exc:
                errors.append({"source": "bikeradar", "url": url, "error": str(exc)})
        path = settings.raw_crawl_dir / f"{run_at}_bikeradar.jsonl"
        write_jsonl(path, rows)
        results.append({"source": "bikeradar", "count": len(rows), "path": str(path)})

    print(json.dumps({"results": results, "errors": errors}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
