from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.collectors.api_bike_index import BikeIndexCollector
from bike_data_platform.collectors.static_pages import BikeComponentsCollector, BikeRadarCollector
from bike_data_platform.settings import get_settings
from bike_data_platform.storage import write_jsonl
from bike_data_platform.transformers.unified_warehouse import build_unified_warehouse
from bike_data_platform.transformers.warehouse import build_warehouse


def _run_bike_index(settings, cfg: dict, run_at: str, max_pages: int | None, queries: list[str] | None) -> dict:
    cache_dir = settings.bronze_dir / "http_cache" / "bike_index"
    cache_dir.mkdir(parents=True, exist_ok=True)
    collector = BikeIndexCollector(
        base_url=cfg["base_url"],
        user_agent=cfg["user_agent"],
        cache_dir=cache_dir,
        per_page=int(cfg.get("per_page", 25)),
        max_pages=max_pages or int(cfg.get("max_pages", 3)),
    )
    manufacturer_rows = collector.fetch_manufacturers()
    manufacturer_path = settings.raw_crawl_dir / f"{run_at}_bike_index_manufacturers.jsonl"
    write_jsonl(manufacturer_path, manufacturer_rows)

    bike_rows = []
    for query in queries or cfg.get("search_queries", []):
        bike_rows.extend(collector.search_bikes(query))
    bike_path = settings.raw_crawl_dir / f"{run_at}_bike_index_bikes.jsonl"
    write_jsonl(bike_path, bike_rows)
    return {
        "source": "bike_index",
        "files": [
            {"name": "bike_index_manufacturers", "count": len(manufacturer_rows), "path": str(manufacturer_path)},
            {"name": "bike_index_bikes", "count": len(bike_rows), "path": str(bike_path)},
        ],
    }


def _run_static_source(settings, source_name: str, cfg: dict, run_at: str) -> dict:
    cache_dir = settings.bronze_dir / "http_cache" / source_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    if source_name == "bike_components":
        collector = BikeComponentsCollector(
            user_agent=cfg["user_agent"],
            cache_dir=cache_dir,
        )
    elif source_name == "bikeradar":
        collector = BikeRadarCollector(
            user_agent=cfg["user_agent"],
            cache_dir=cache_dir,
        )
    else:
        raise ValueError(f"Unsupported source: {source_name}")

    rows = []
    errors = []
    for url in cfg.get("start_urls", []):
        try:
            rows.extend(collector.fetch(url))
        except Exception as exc:  # pragma: no cover - network dependent
            errors.append({"source": source_name, "url": url, "error": str(exc)})
    path = settings.raw_crawl_dir / f"{run_at}_{source_name}.jsonl"
    write_jsonl(path, rows)
    return {
        "source": source_name,
        "files": [{"name": source_name, "count": len(rows), "path": str(path)}],
        "errors": errors,
    }


def _ingest(settings) -> dict:
    warehouse_result = build_warehouse(
        raw_crawl_dir=settings.raw_crawl_dir,
        db_path=settings.warehouse_db_path,
        schema_path=settings.schema_path,
    )
    unified_result = build_unified_warehouse(
        project_root=settings.project_root,
        general_db_path=settings.warehouse_db_path,
        official_db_path=settings.official_warehouse_db_path,
        unified_db_path=settings.unified_warehouse_db_path,
        schema_path=settings.unified_schema_path,
    )
    return {
        "warehouse": warehouse_result,
        "unified_warehouse": unified_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="按来源逐步扩抓公开源，并可在每一步后增量入库")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["bike_index", "bike_components", "bikeradar"],
        default=["bike_index", "bike_components", "bikeradar"],
        help="要执行的公开来源",
    )
    parser.add_argument("--ingest", action="store_true", help="抓取完成后重建基础库与统一库")
    parser.add_argument("--ingest-after-each", action="store_true", help="每个来源抓完后立即入库")
    parser.add_argument("--bike-index-max-pages", type=int, help="覆盖 Bike Index 的最大页数")
    parser.add_argument("--bike-index-queries", nargs="*", help="覆盖 Bike Index 的搜索词")
    args = parser.parse_args()

    settings = get_settings()
    cfg = settings.config["collectors"]
    run_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    results = []
    all_errors = []
    ingestion_results = []

    for source_name in args.sources:
        if source_name == "bike_index":
            result = _run_bike_index(
                settings=settings,
                cfg=cfg["bike_index"],
                run_at=run_at,
                max_pages=args.bike_index_max_pages,
                queries=args.bike_index_queries,
            )
        else:
            result = _run_static_source(
                settings=settings,
                source_name=source_name,
                cfg=cfg[source_name],
                run_at=run_at,
            )
        results.append(result)
        all_errors.extend(result.get("errors", []))

        if args.ingest_after_each:
            ingestion_results.append(
                {
                    "after_source": source_name,
                    "result": _ingest(settings),
                }
            )

    if args.ingest and not args.ingest_after_each:
        ingestion_results.append(
            {
                "after_source": "all",
                "result": _ingest(settings),
            }
        )

    print(
        json.dumps(
            {
                "results": results,
                "errors": all_errors,
                "ingestion_results": ingestion_results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
