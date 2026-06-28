from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.transformers.website_api import export_website_api


def _export_table(conn: sqlite3.Connection, query: str, json_path: Path, csv_path: Path) -> int:
    conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.execute(query).fetchall()]
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)
    return len(rows)


def main() -> None:
    export_dir = ROOT / "data" / "gold" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, int | str] = {}
    unified_db = ROOT / "data" / "gold" / "bicycle_unified_warehouse.db"

    if unified_db.exists():
        conn = sqlite3.connect(unified_db)
        summary["vw_bike_core"] = _export_table(
            conn,
            "SELECT * FROM vw_bike_core",
            export_dir / "vw_bike_core.json",
            export_dir / "vw_bike_core.csv",
        )
        summary["vw_component_core"] = _export_table(
            conn,
            "SELECT * FROM vw_component_core",
            export_dir / "vw_component_core.json",
            export_dir / "vw_component_core.csv",
        )
        summary["vw_bike_part_heatmap"] = _export_table(
            conn,
            "SELECT * FROM vw_bike_part_heatmap",
            export_dir / "vw_bike_part_heatmap.json",
            export_dir / "vw_bike_part_heatmap.csv",
        )
        conn.close()
        summary.update(export_website_api(unified_db, export_dir))
    else:
        official_db = ROOT / "data" / "gold" / "official_bike_warehouse.db"
        if official_db.exists():
            conn = sqlite3.connect(official_db)
            summary["official_bike_rows"] = _export_table(
                conn,
                "SELECT * FROM official_bike_rows",
                export_dir / "official_bike_rows.json",
                export_dir / "official_bike_rows.csv",
            )
            summary["official_component_rows"] = _export_table(
                conn,
                "SELECT * FROM official_component_rows",
                export_dir / "official_component_rows.json",
                export_dir / "official_component_rows.csv",
            )
            conn.close()

    general_db = ROOT / "data" / "gold" / "bicycle_warehouse.db"
    if general_db.exists():
        conn = sqlite3.connect(general_db)
        summary["components"] = _export_table(
            conn,
            "SELECT * FROM components",
            export_dir / "components.json",
            export_dir / "components.csv",
        )
        summary["reviews"] = _export_table(
            conn,
            "SELECT * FROM reviews",
            export_dir / "reviews.json",
            export_dir / "reviews.csv",
        )
        conn.close()

    (export_dir / "project_export_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
