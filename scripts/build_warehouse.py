from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.settings import get_settings
from bike_data_platform.transformers.warehouse import build_warehouse


def main() -> None:
    settings = get_settings()
    result = build_warehouse(
        raw_crawl_dir=settings.raw_crawl_dir,
        db_path=settings.warehouse_db_path,
        schema_path=settings.schema_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
