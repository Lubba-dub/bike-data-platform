from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Settings:
    project_root: Path
    config_path: Path
    raw_datasets_dir: Path
    raw_crawl_dir: Path
    bronze_dir: Path
    silver_dir: Path
    gold_dir: Path
    logs_dir: Path
    warehouse_db_path: Path
    schema_path: Path
    official_warehouse_db_path: Path
    unified_warehouse_db_path: Path
    unified_schema_path: Path
    config: dict


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "config" / "sources.yaml"
    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    return Settings(
        project_root=project_root,
        config_path=config_path,
        raw_datasets_dir=project_root / "data" / "raw" / "datasets",
        raw_crawl_dir=project_root / "data" / "raw" / "crawl",
        bronze_dir=project_root / "data" / "bronze",
        silver_dir=project_root / "data" / "silver",
        gold_dir=project_root / "data" / "gold",
        logs_dir=project_root / "logs",
        warehouse_db_path=project_root / "data" / "gold" / "bicycle_warehouse.db",
        schema_path=project_root / "sql" / "schema.sql",
        official_warehouse_db_path=project_root / "data" / "gold" / "official_bike_warehouse.db",
        unified_warehouse_db_path=project_root / "data" / "gold" / "bicycle_unified_warehouse.db",
        unified_schema_path=project_root / "sql" / "unified_schema.sql",
        config=config,
    )
