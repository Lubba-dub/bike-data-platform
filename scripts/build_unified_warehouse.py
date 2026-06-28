from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.settings import get_settings
from bike_data_platform.transformers.unified_warehouse import build_unified_warehouse


def main() -> None:
    settings = get_settings()
    result = build_unified_warehouse(
        project_root=settings.project_root,
        general_db_path=settings.warehouse_db_path,
        official_db_path=settings.official_warehouse_db_path,
        unified_db_path=settings.unified_warehouse_db_path,
        schema_path=settings.unified_schema_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
