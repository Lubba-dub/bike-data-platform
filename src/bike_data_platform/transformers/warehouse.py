from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from bike_data_platform.storage import connect_db, initialize_schema, read_jsonl


def parse_price_value(price_text: str | None) -> tuple[float | None, str | None]:
    if not price_text:
        return None, None
    currency = None
    if "€" in price_text:
        currency = "EUR"
    elif "£" in price_text:
        currency = "GBP"
    elif "$" in price_text:
        currency = "USD"
    match = re.search(r"(\d[\d,\.]*)", price_text.replace(",", ""))
    if not match:
        return None, currency
    try:
        return float(match.group(1)), currency
    except ValueError:
        return None, currency


def parse_rating_value(rating_text: str | None) -> tuple[float | None, int | None]:
    if not rating_text:
        return None, None
    rating_match = re.search(r"Rating:\s*([\d\.]+)", rating_text)
    count_match = re.search(r"based on\s*(\d+)\s*reviews?", rating_text)
    rating_value = float(rating_match.group(1)) if rating_match else None
    review_count = int(count_match.group(1)) if count_match else None
    return rating_value, review_count


def latest_raw_files(raw_crawl_dir: Path) -> list[Path]:
    groups: dict[str, Path] = {}
    for path in sorted(raw_crawl_dir.glob("*.jsonl")):
        stem = path.stem
        source_key = stem.split("_", 1)[1] if "_" in stem else stem
        groups[source_key] = path
    return sorted(groups.values())


def build_warehouse(raw_crawl_dir: Path, db_path: Path, schema_path: Path) -> dict:
    if db_path.exists():
        db_path.unlink()
    conn = connect_db(db_path)
    initialize_schema(conn, schema_path)

    inserted = {"manufacturers": 0, "bikes": 0, "components": 0, "reviews": 0}
    for path in latest_raw_files(raw_crawl_dir):
        rows = read_jsonl(path)
        for row in rows:
            entity = row.get("entity")
            payload_json = json.dumps(row.get("payload", {}), ensure_ascii=False)
            if entity == "manufacturer":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO manufacturers(source, source_id, name, slug, url, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source"),
                        row.get("source_id"),
                        row.get("name"),
                        row.get("slug"),
                        row.get("url"),
                        payload_json,
                    ),
                )
                inserted["manufacturers"] += 1
            elif entity == "bike":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO bikes(source, source_id, title, manufacturer, frame_model, year,
                    description, category, price_text, rating_text, url, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source"),
                        row.get("source_id"),
                        row.get("title"),
                        row.get("manufacturer_name"),
                        row.get("frame_model"),
                        row.get("year"),
                        row.get("description"),
                        row.get("query"),
                        row.get("price_text"),
                        row.get("rating_text"),
                        row.get("url"),
                        payload_json,
                    ),
                )
                inserted["bikes"] += 1
            elif entity == "component":
                price_value, currency = parse_price_value(row.get("price_text"))
                rating_value, review_count = parse_rating_value(row.get("rating_text"))
                manufacturer = row.get("manufacturer")
                name = row.get("name") or ""
                if not manufacturer and " " in name:
                    manufacturer = name.split(" ", 1)[0]
                conn.execute(
                    """
                    INSERT OR REPLACE INTO components(source, source_id, name, manufacturer, category,
                    price_text, price_value, currency, rating_text, rating_value, review_count, url, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source"),
                        row.get("source_id"),
                        name,
                        manufacturer,
                        row.get("category"),
                        row.get("price_text"),
                        price_value,
                        currency,
                        row.get("rating_text"),
                        rating_value,
                        review_count,
                        row.get("url"),
                        payload_json,
                    ),
                )
                inserted["components"] += 1
            elif entity == "review":
                price_value, _ = parse_price_value(row.get("price_text"))
                brand_hint = row.get("brand_hint")
                title = row.get("title") or ""
                if not brand_hint and title:
                    brand_hint = title.split(" ", 1)[0]
                review_payload = {
                    **(row.get("payload", {}) or {}),
                    "rating_value": row.get("rating_value"),
                    "rating_scale": row.get("rating_scale"),
                    "brand_hint": brand_hint,
                }
                conn.execute(
                    """
                    INSERT OR REPLACE INTO reviews(source, source_id, title, summary, category, subtype,
                    brand_hint, price_text, price_value, url, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source"),
                        row.get("source_id"),
                        title,
                        row.get("summary"),
                        row.get("category"),
                        row.get("subtype"),
                        brand_hint,
                        row.get("price_text"),
                        price_value,
                        row.get("url"),
                        json.dumps(review_payload, ensure_ascii=False),
                    ),
                )
                inserted["reviews"] += 1

    conn.commit()

    summary = {}
    for table in ["manufacturers", "bikes", "components", "reviews"]:
        summary[table] = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]

    component_df = pd.read_sql_query(
        """
        SELECT COALESCE(manufacturer, 'UNKNOWN') AS manufacturer, category, price_value
        FROM components
        WHERE price_value IS NOT NULL
        """,
        conn,
    )
    if not component_df.empty:
        brand_summary = (
            component_df.groupby("manufacturer", as_index=False)
            .agg(product_count=("price_value", "count"), avg_price=("price_value", "mean"))
            .sort_values(["product_count", "avg_price"], ascending=[False, False])
        )
        brand_summary.to_csv(db_path.parent / "brand_price_summary.csv", index=False, encoding="utf-8-sig")

        category_summary = (
            component_df.groupby("category", as_index=False)
            .agg(product_count=("price_value", "count"), avg_price=("price_value", "mean"))
            .sort_values(["product_count", "avg_price"], ascending=[False, False])
        )
        category_summary.to_csv(db_path.parent / "category_price_summary.csv", index=False, encoding="utf-8-sig")

    conn.close()
    return {"inserted": inserted, "summary": summary}
