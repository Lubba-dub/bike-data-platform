from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.settings import get_settings


def query_one(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def main() -> None:
    settings = get_settings()
    conn = sqlite3.connect(settings.warehouse_db_path)

    summary = {
        "manufacturers": query_one(conn, "SELECT COUNT(*) FROM manufacturers"),
        "bikes": query_one(conn, "SELECT COUNT(*) FROM bikes"),
        "components": query_one(conn, "SELECT COUNT(*) FROM components"),
        "reviews": query_one(conn, "SELECT COUNT(*) FROM reviews"),
        "priced_components": query_one(conn, "SELECT COUNT(*) FROM components WHERE price_value IS NOT NULL"),
    }

    top_brands = conn.execute(
        """
        SELECT COALESCE(manufacturer, 'UNKNOWN') AS manufacturer, COUNT(*) AS cnt,
               ROUND(AVG(price_value), 2) AS avg_price
        FROM components
        WHERE price_value IS NOT NULL
        GROUP BY COALESCE(manufacturer, 'UNKNOWN')
        ORDER BY cnt DESC, avg_price DESC
        LIMIT 20
        """
    ).fetchall()

    category_stats = conn.execute(
        """
        SELECT COALESCE(category, 'UNKNOWN') AS category, COUNT(*) AS cnt,
               ROUND(AVG(price_value), 2) AS avg_price
        FROM components
        WHERE price_value IS NOT NULL
        GROUP BY COALESCE(category, 'UNKNOWN')
        ORDER BY cnt DESC, avg_price DESC
        """
    ).fetchall()

    payload = {
        "summary": summary,
        "top_brands": [
            {"manufacturer": row[0], "count": row[1], "avg_price": row[2]}
            for row in top_brands
        ],
        "category_stats": [
            {"category": row[0], "count": row[1], "avg_price": row[2]}
            for row in category_stats
        ],
    }

    output_path = settings.gold_dir / "analysis_summary.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
