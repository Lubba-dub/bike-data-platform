from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.collectors.official_sites import BrandCrawler
from bike_data_platform.http_client import SimpleHttpClient
from bike_data_platform.settings import get_settings
from bike_data_platform.storage import write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取品牌官网自行车与配件数据")
    parser.add_argument("--brands", nargs="*", help="仅抓取指定品牌，如 giant merida brompton")
    parser.add_argument("--max-products-per-brand", type=int, help="覆盖配置中的每品牌抓取上限")
    args = parser.parse_args()

    settings = get_settings()
    config_path = settings.project_root / "config" / "official_sites.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    crawler_cfg = config["official_collectors"]
    run_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    results = []
    errors = []
    rows = []

    cache_root = settings.bronze_dir / "http_cache" / "official_sites"
    user_agent = crawler_cfg["user_agent"]
    max_depth = int(crawler_cfg.get("max_depth", 1))
    max_products_per_brand = int(args.max_products_per_brand or crawler_cfg.get("max_products_per_brand", 80))
    sleep_seconds = float(crawler_cfg.get("request_sleep_seconds", 0.6))
    selected_brands = {brand.lower() for brand in args.brands} if args.brands else None

    for brand_cfg in crawler_cfg["brands"]:
        if not brand_cfg.get("enabled", True):
            continue
        brand = brand_cfg["brand"]
        if selected_brands and brand.lower() not in selected_brands:
            continue
        client = SimpleHttpClient(
            user_agent=user_agent,
            cache_dir=cache_root / brand,
            sleep_seconds=sleep_seconds,
        )
        crawler = BrandCrawler(
            brand=brand,
            base_url=brand_cfg["base_url"],
            entity_type=brand_cfg.get("entity_type", "bike"),
            start_urls=brand_cfg["start_urls"],
            include_patterns=brand_cfg.get("include_patterns", []),
            product_url_patterns=brand_cfg.get("product_url_patterns", []),
            exclude_url_patterns=brand_cfg.get("exclude_url_patterns", []),
            discovery_regexes=brand_cfg.get("discovery_regexes", []),
            inline_products=bool(brand_cfg.get("inline_products", False)),
            max_depth=max_depth,
            max_products=max_products_per_brand,
            client=client,
        )
        try:
            brand_rows = crawler.crawl()
            rows.extend(brand_rows)
            results.append({"brand": brand, "count": len(brand_rows)})
        except Exception as exc:
            errors.append({"brand": brand, "error": str(exc)})

    output_path = settings.raw_crawl_dir / f"{run_at}_official_sites.jsonl"
    write_jsonl(output_path, rows)
    print(json.dumps({"results": results, "errors": errors, "path": str(output_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
