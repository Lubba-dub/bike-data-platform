from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.collectors.browser_officials import BrowserBrandCrawler
from bike_data_platform.settings import get_settings
from bike_data_platform.storage import write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="使用浏览器自动化抓取品牌官网产品")
    parser.add_argument("--brands", nargs="*", help="仅抓取指定品牌，如 shimano giant oyama")
    parser.add_argument("--max-products-per-brand", type=int, default=12)
    parser.add_argument("--headless", action="store_true", help="启用无头浏览器")
    args = parser.parse_args()

    settings = get_settings()
    config = yaml.safe_load((settings.project_root / "config" / "official_sites.yaml").read_text(encoding="utf-8"))
    brand_configs = config["official_collectors"]["brands"]
    selected = {brand.lower() for brand in args.brands} if args.brands else None

    run_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    rows: list[dict] = []
    results: list[dict] = []
    errors: list[dict] = []

    for brand_cfg in brand_configs:
        brand = brand_cfg["brand"]
        if selected and brand.lower() not in selected:
            continue
        crawler = BrowserBrandCrawler(
            brand=brand,
            base_url=brand_cfg["base_url"],
            entity_type=brand_cfg.get("entity_type", "bike"),
            start_urls=brand_cfg["start_urls"],
            include_patterns=brand_cfg.get("include_patterns", []),
            product_url_patterns=brand_cfg.get("product_url_patterns", []),
            discovery_regexes=brand_cfg.get("discovery_regexes", []),
            max_discovery_depth=brand_cfg.get("max_discovery_depth", 1),
            max_products=args.max_products_per_brand,
            headless=args.headless,
        )
        brand_rows, brand_errors = crawler.crawl()
        rows.extend(brand_rows)
        errors.extend(brand_errors)
        results.append({"brand": brand, "count": len(brand_rows), "errors": len(brand_errors)})

    output_path = settings.raw_crawl_dir / f"{run_at}_official_sites_browser.jsonl"
    write_jsonl(output_path, rows)
    (settings.raw_crawl_dir / f"{run_at}_official_sites_browser_errors.json").write_text(
        json.dumps(errors, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"results": results, "errors": errors[:10], "path": str(output_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
