from __future__ import annotations

import json
import sqlite3
from pathlib import Path

VISUAL_PART_FALLBACKS = (
    "frame",
    "fork",
    "brake",
    "tyre",
    "seatpost",
    "shock",
    "derailleur",
    "cassette",
    "crankset",
    "handlebar",
    "saddle",
    "pedal",
    "shifter",
)

FRAME_TECH_SPEC_NAMES = {
    "frame technology",
}

FRAME_TECH_VALUE_TOKENS = (
    "fast kinematic",
    "hfs",
    "internal cable routing",
    "long fender",
    "non-slip tightening",
    "p-flex",
    "smooth welding",
    "wire port",
    "x-taper",
    "anti wrinkle",
    "service port",
    "nano matrix",
)

FRAME_NAVIGATION_VALUE_TOKENS = (
    "shop ",
    "learn about",
    "need help",
    "bike finder",
    "generations",
)

NOISY_COMPONENT_VALUE_TOKENS = (
    "rating:",
    "reviews (",
    "show more",
    "read more",
    "instead of",
    "quickly sold out",
    "back in stock",
    "new rating",
    "up to -",
)

MOUNTAIN_COMPONENT_HINTS = {
    "fork": ("rockshox", "fox", "marzocchi", "zeb", "lyrik", "pike", '36', '38', "suspension fork"),
    "brake": ("disc brake", "hydraulic", "tektro", "magura", "shimano", "sram"),
    "cassette": ("deore", "slx", "xt", "xtr", "gx", "nx", "eagle", "speed cassette"),
    "derailleur": ("deore", "slx", "xt", "xtr", "gx", "nx", "eagle", "rd-"),
    "shifter": ("trigger", "deore", "slx", "xt", "gx", "axs", "revoshift"),
    "tyre": ("maxxis", "schwalbe", "continental", "pirelli", "michelin", "tyre", "tire"),
    "shock": ("rockshox", "fox", "marzocchi", "super deluxe", "vivid", "air shock", "rear shock"),
    "seatpost": ("dropper", "transfer", "reverb", "vyron", "seatpost"),
}

COMPONENT_ONLY_BRANDS = {
    "sram",
    "shimano",
}

NON_BIKE_VARIANT_TOKENS = (
    "transmission",
    "drivetrain",
    "powertrain",
    "brakes",
    "groupset",
    "cassette",
    "derailleur",
    "chainring",
)


def _infer_bike_type(
    brand: str | None,
    family_name: str | None,
    model_name: str | None,
    variant_name: str | None,
    official_url: str | None,
    description: str | None,
) -> str:
    text = " ".join(
        str(value or "")
        for value in (brand, family_name, model_name, variant_name, official_url, description)
    ).lower()
    if any(token in text for token in ("fold", "brompton", "dahon", "fnhon", "oyama")):
        return "folding"
    if any(
        token in text
        for token in (
            "mountain",
            "mtb",
            "trail",
            "enduro",
            "downhill",
            "xc",
            "cross-country",
            "all-mountain",
            "one-twenty",
            "one-sixty",
            "one-forty",
            "ninety-six",
            "big.trail",
            "big nine",
            "big.nine",
            "slash",
            "fuel exe",
            "top fuel",
            "supercaliber",
            "roscoe",
            "marlin",
            "spectral",
            "neuron",
            "lux",
            "stoic",
            "sender",
            "torque",
            "strive",
            "grand canyon",
            "habit",
            "scalpel",
            "jekyll",
            "moterra",
            "f-si",
        )
    ):
        return "mountain"
    if any(token in text for token in ("gravel", "silex")):
        return "gravel"
    if any(token in text for token in ("city", "urban", "commuter", "hybrid", "touring")):
        return "city"
    if any(token in text for token in ("road", "race", "endurance", "aero", "reacto", "scultura", "endurace", "madone", "domane")):
        return "road"
    if any(token in text for token in ("electric", "e-bike", "ebike")):
        return "electric"
    return "other"


def _template_type_from_bike_type(bike_type: str) -> str:
    return "mountain" if bike_type == "mountain" else "road"


def _latest_snapshot_date(conn: sqlite3.Connection, table_name: str) -> str | None:
    row = conn.execute(f"SELECT MAX(snapshot_date) FROM {table_name}").fetchone()
    return row[0] if row and row[0] else None


def _row_to_view_map(rows: list[sqlite3.Row]) -> dict[str, str | None]:
    views = {"front": None, "side": None, "rear": None}
    for row in rows:
        view_type = row["view_type"]
        view_value = row["original_url"] or row["local_path"]
        if view_type in views and view_value:
            views[view_type] = view_value
        elif not views["side"] and view_value:
            views["side"] = view_value
    return views


def _metric_value(primary: dict, fallback: dict, row: sqlite3.Row, key: str, row_key: str | None = None):
    metric_key = row_key or key
    value = primary.get(key)
    if value is not None:
        return value
    value = fallback.get(key)
    if value is not None:
        return value
    return row[metric_key]


def _normalize_part_key(part_key: str | None, spec_name: str | None, spec_value: str | None, component_name: str | None) -> str:
    normalized = str(part_key or "").strip().lower()
    text = " ".join(str(value or "").lower() for value in (spec_name, spec_value, component_name))
    if "seatpost" in text or "dropper" in text:
        return "seatpost"
    if normalized == "wheel":
        return "tyre"
    if normalized == "groupset":
        return "derailleur"
    return normalized


def _canonical_part_name(part_key: str) -> str:
    return {
        "brake": "Brake",
        "cassette": "Cassette",
        "chain": "Chain",
        "crankset": "Crankset",
        "derailleur": "Derailleur",
        "fork": "Fork",
        "frame": "Frame",
        "handlebar": "Handlebar",
        "pedal": "Pedal",
        "saddle": "Saddle",
        "seatpost": "Seatpost",
        "shifter": "Shifter",
        "shock": "Shock",
        "tyre": "Tyre",
        "wheel": "Wheel",
    }.get(part_key, part_key.replace("_", " ").title())


def _display_component_value(
    part_key: str,
    spec_name: str | None,
    spec_value: str | None,
    component_name: str | None,
) -> str | None:
    name = str(component_name or "").strip()
    value = str(spec_value or "").strip()
    spec = str(spec_name or "").strip()
    if part_key == "seatpost" and spec.lower().startswith("travel seatpost"):
        return f"Travel seatpost {value}".strip()
    return name or value or None


def _average_metric(rows: list[dict], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _clean_component_display_name(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"n/a", "na", "none"}:
        return None
    if any(token in lowered for token in NOISY_COMPONENT_VALUE_TOKENS):
        return None
    if len(text) > 96:
        return None
    return text


def _representative_component_rank(row: dict, bike_type: str, part_key: str) -> tuple[int, int, int, int, int]:
    component_name = str(row.get("component_name") or "")
    brand_name = str(row.get("brand_name") or "")
    lowered = f"{brand_name} {component_name}".lower()
    hints = MOUNTAIN_COMPONENT_HINTS.get(part_key, ()) if bike_type == "mountain" else ()
    hint_score = sum(1 for hint in hints if hint and hint in lowered)
    cleaned_name = _clean_component_display_name(component_name)
    readable = int(cleaned_name is not None)
    has_metric = int(
        row.get("price_score") is not None
        or row.get("quality_score") is not None
        or row.get("value_score") is not None
    )
    reviews = int(row.get("reviews_count") or 0)
    offers = int(row.get("offers_count") or 0)
    text_len = len(cleaned_name or component_name)
    compactness = -abs(text_len - 28)
    return (hint_score, readable, has_metric, reviews + offers, compactness)


def _build_part_metric_defaults(conn: sqlite3.Connection, snapshot_date: str | None) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT
            pt.part_key,
            cc.component_name,
            br.brand_name,
            cms.offer_count,
            cms.review_count,
            cms.price_score,
            cms.quality_score,
            cms.value_score
        FROM component_metric_snapshot cms
        JOIN component_catalog cc
          ON cc.component_catalog_id = cms.component_catalog_id
        JOIN part_taxonomy pt
          ON pt.part_taxonomy_id = cc.part_taxonomy_id
        LEFT JOIN brand br
          ON br.brand_id = cc.brand_id
        WHERE cms.snapshot_date = ?
        """,
        (snapshot_date,),
    ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["part_key"], []).append(
            {
                "component_name": row["component_name"],
                "brand_name": row["brand_name"],
                "offers_count": row["offer_count"] or 0,
                "reviews_count": row["review_count"] or 0,
                "price_score": row["price_score"],
                "quality_score": row["quality_score"],
                "value_score": row["value_score"],
            }
        )

    defaults: dict[str, dict] = {}
    for part_key, part_rows in grouped.items():
        representative_mountain = max(
            part_rows,
            key=lambda row: _representative_component_rank(row, "mountain", part_key),
        )
        representative_general = max(
            part_rows,
            key=lambda row: _representative_component_rank(row, "other", part_key),
        )
        defaults[part_key] = {
            "offers_count": sum(int(row["offers_count"] or 0) for row in part_rows),
            "reviews_count": sum(int(row["reviews_count"] or 0) for row in part_rows),
            "price_score": _average_metric(part_rows, "price_score"),
            "quality_score": _average_metric(part_rows, "quality_score"),
            "value_score": _average_metric(part_rows, "value_score"),
            "representative_component_name": _clean_component_display_name(representative_general.get("component_name")),
            "representative_brand_name": representative_general.get("brand_name"),
            "mountain_component_name": _clean_component_display_name(representative_mountain.get("component_name")),
            "mountain_brand_name": representative_mountain.get("brand_name"),
        }
    return defaults


def _is_marketing_part_row(part_key: str, spec_name: str | None, spec_value: str | None, component_name: str | None) -> bool:
    if part_key != "frame":
        return False
    name = str(spec_name or "").strip().lower()
    value = " ".join(str(item or "").lower() for item in (spec_value, component_name))
    if name in FRAME_TECH_SPEC_NAMES or any(token in value for token in FRAME_TECH_VALUE_TOKENS):
        return True
    if len(value) > 100 and any(token in value for token in FRAME_NAVIGATION_VALUE_TOKENS):
        return True
    return False


def _part_rank_key(part_row: dict) -> tuple[int, int, int, int, int]:
    offers = int(part_row.get("offers_count") or 0)
    reviews = int(part_row.get("reviews_count") or 0)
    has_metric = int(
        part_row.get("price_score") is not None
        or part_row.get("quality_score") is not None
        or part_row.get("value_score") is not None
    )
    is_inferred = int(bool(part_row.get("is_inferred")))
    text_len = len(str(part_row.get("component_name") or part_row.get("value") or ""))
    readability = 1 if 6 <= text_len <= 60 else 0
    compactness = -abs(text_len - 28)
    return (1 - is_inferred, has_metric, offers + reviews, readability, compactness)


def _compress_bike_parts(
    parts: list[dict],
    bike_type: str,
    part_metric_defaults: dict[str, dict],
    bike_name: str | None = None,
    brand_name: str | None = None,
) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for part in parts:
        part_key = _normalize_part_key(
            part.get("part_key"),
            part.get("spec_name"),
            part.get("value"),
            part.get("component_name"),
        )
        if not part_key:
            continue
        candidate = {**part, "part_key": part_key}
        if _is_marketing_part_row(part_key, part.get("spec_name"), part.get("value"), part.get("component_name")):
            candidate["is_marketing"] = True
        grouped.setdefault(part_key, []).append(candidate)

    cleaned: list[dict] = []
    for part_key, rows in grouped.items():
        useful_rows = [row for row in rows if not row.get("is_marketing")]
        source_rows = useful_rows or rows
        if not useful_rows and bike_type == "mountain":
            source_rows = []
        if not source_rows:
            continue
        best = max(source_rows, key=_part_rank_key)
        cleaned.append(
            {
                **{
                    key: value
                    for key, value in best.items()
                    if key not in {"is_marketing"}
                },
                "part_key": part_key,
                "name": _canonical_part_name(part_key),
                "slot": part_key,
            }
        )

    observed_keys = {row["part_key"] for row in cleaned}
    if bike_type == "mountain" and len(observed_keys) < 4:
        for part_key in VISUAL_PART_FALLBACKS:
            if part_key in observed_keys:
                continue
            if part_key == "frame":
                continue
            metric = part_metric_defaults.get(part_key)
            if not metric:
                continue
            representative_component = metric.get("mountain_component_name") or metric.get("representative_component_name")
            representative_brand = metric.get("mountain_brand_name") or metric.get("representative_brand_name")
            if (
                metric.get("price_score") is None
                and metric.get("quality_score") is None
                and metric.get("value_score") is None
                and not representative_component
            ):
                continue
            cleaned.append(
                {
                    "part_key": part_key,
                    "name": _canonical_part_name(part_key),
                    "value": f"{_canonical_part_name(part_key)} representative fallback",
                    "slot": part_key,
                    "brand_hint": representative_brand or "database representative",
                    "component_name": f"{_canonical_part_name(part_key)} representative fallback",
                    "spec_name": "database representative fallback",
                    "offers_count": metric.get("offers_count") or 0,
                    "reviews_count": metric.get("reviews_count") or 0,
                    "price_score": metric.get("price_score"),
                    "quality_score": metric.get("quality_score"),
                    "value_score": metric.get("value_score"),
                    "is_inferred": True,
                }
            )
        observed_keys = {row["part_key"] for row in cleaned}
    if bike_type == "mountain" and "frame" not in observed_keys:
        price_values = [float(row["price_score"]) for row in cleaned if row.get("price_score") is not None]
        quality_values = [float(row["quality_score"]) for row in cleaned if row.get("quality_score") is not None]
        value_values = [float(row["value_score"]) for row in cleaned if row.get("value_score") is not None]
        if price_values or quality_values or value_values:
            cleaned.append(
                {
                    "part_key": "frame",
                    "name": "Frame",
                    "value": f"{bike_name or 'bike'} frame",
                    "slot": "frame",
                    "brand_hint": brand_name or "bike structure",
                    "component_name": f"{bike_name or 'bike'} frame",
                    "spec_name": "bike structure fallback",
                    "offers_count": 0,
                    "reviews_count": 0,
                    "price_score": (sum(price_values) / len(price_values)) if price_values else None,
                    "quality_score": (sum(quality_values) / len(quality_values)) if quality_values else None,
                    "value_score": (sum(value_values) / len(value_values)) if value_values else None,
                    "is_inferred": True,
                }
            )
    if bike_type == "mountain":
        price_values = [float(row["price_score"]) for row in cleaned if row.get("price_score") is not None]
        quality_values = [float(row["quality_score"]) for row in cleaned if row.get("quality_score") is not None]
        value_values = [float(row["value_score"]) for row in cleaned if row.get("value_score") is not None]
        price_fill = (sum(price_values) / len(price_values)) if price_values else None
        quality_fill = (sum(quality_values) / len(quality_values)) if quality_values else None
        value_fill = (sum(value_values) / len(value_values)) if value_values else None
        for row in cleaned:
            if row.get("price_score") is None and price_fill is not None:
                row["price_score"] = price_fill
            if row.get("quality_score") is None and quality_fill is not None:
                row["quality_score"] = quality_fill
            if row.get("value_score") is None and value_fill is not None:
                row["value_score"] = value_fill
    cleaned.sort(key=lambda item: (item["part_key"], -int(item.get("offers_count") or 0), -int(item.get("reviews_count") or 0)))
    return cleaned


def _should_export_bike_record(bike: sqlite3.Row, bike_type: str) -> bool:
    brand = str(bike["brand_name"] or "").strip().lower()
    variant = str(bike["variant_name"] or "").strip().lower()
    model = str(bike["model_name"] or "").strip().lower()
    family = str(bike["family_name"] or "").strip().lower()
    url = str(bike["official_url"] or "").strip().lower()
    if brand in COMPONENT_ONLY_BRANDS:
        return False
    if any(token in f"{variant} {model} {family}" for token in NON_BIKE_VARIANT_TOKENS):
        return False
    if brand in {"fox", "rockshox", "dt swiss"} and not any(token in url for token in ("/bike/", "/bikes/")):
        return False
    return True


def export_website_api(db_path: Path, export_dir: Path) -> dict[str, int]:
    export_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    bike_snapshot_date = _latest_snapshot_date(conn, "bike_part_metric_snapshot")
    component_snapshot_date = _latest_snapshot_date(conn, "component_metric_snapshot")
    part_metric_defaults = _build_part_metric_defaults(conn, component_snapshot_date)

    bikes = conn.execute(
        """
        SELECT * FROM vw_bike_core
        ORDER BY brand_name, model_name, variant_name
        """
    ).fetchall()
    bikes_payload = []
    parts_payload = []

    for bike in bikes:
        bike_type = _infer_bike_type(
            bike["brand_name"],
            bike["family_name"],
            bike["model_name"],
            bike["variant_name"],
            bike["official_url"],
            bike["description"],
        )
        if not _should_export_bike_record(bike, bike_type):
            continue
        template_type = _template_type_from_bike_type(bike_type)
        media_rows = conn.execute(
            """
            SELECT bm.view_type, ma.original_url, ma.local_path
            FROM bike_media bm
            JOIN media_asset ma
              ON ma.media_id = bm.media_id
            WHERE bm.bike_variant_id = ?
            ORDER BY bm.sort_order
            """,
            (bike["bike_variant_id"],),
        ).fetchall()
        views = _row_to_view_map(media_rows)

        component_rows = conn.execute(
            """
            SELECT
                bbc.slot_name,
                bbc.spec_name,
                bbc.spec_value,
                bbc.inferred_brand_text,
                pt.part_key,
                pt.part_name,
                cc.component_catalog_id,
                cc.component_name,
                cms.offer_count,
                cms.review_count,
                cms.price_score,
                cms.quality_score,
                cms.value_score
            FROM bike_build_component bbc
            JOIN part_taxonomy pt
              ON pt.part_taxonomy_id = bbc.part_taxonomy_id
            LEFT JOIN component_catalog cc
              ON cc.component_catalog_id = bbc.component_catalog_id
            LEFT JOIN component_metric_snapshot cms
              ON cms.component_catalog_id = cc.component_catalog_id
             AND cms.snapshot_date = ?
            WHERE bbc.bike_variant_id = ?
            ORDER BY pt.part_key, cc.component_name, bbc.spec_name
            """,
            (component_snapshot_date, bike["bike_variant_id"]),
        ).fetchall()

        metric_rows = conn.execute(
            """
            SELECT
                pt.part_key,
                pt.part_name,
                bpm.offer_count,
                bpm.review_count,
                bpm.price_score,
                bpm.quality_score,
                bpm.value_score,
                cc.component_name
            FROM bike_part_metric_snapshot bpm
            JOIN part_taxonomy pt
              ON pt.part_taxonomy_id = bpm.part_taxonomy_id
            LEFT JOIN component_catalog cc
              ON cc.component_catalog_id = bpm.component_catalog_id
            WHERE bpm.bike_variant_id = ? AND bpm.snapshot_date = ?
            ORDER BY pt.part_key
            """,
            (bike["bike_variant_id"], bike_snapshot_date),
        ).fetchall()

        component_ids = sorted(
            {
                int(row["component_catalog_id"])
                for row in component_rows
                if row["component_catalog_id"] is not None
            }
        )

        raw_parts = []
        offers = []
        reviews = []
        metric_map = {
            row["part_key"]: {
                "offers_count": row["offer_count"],
                "reviews_count": row["review_count"],
                "price_score": row["price_score"],
                "quality_score": row["quality_score"],
                "value_score": row["value_score"],
                "component_name": row["component_name"],
            }
            for row in metric_rows
        }

        for row in component_rows:
            normalized_part_key = _normalize_part_key(
                row["part_key"],
                row["spec_name"],
                row["spec_value"],
                row["component_name"],
            )
            metric = metric_map.get(row["part_key"], {}) if normalized_part_key == row["part_key"] else {}
            default_metric = part_metric_defaults.get(normalized_part_key, {})
            part_row = {
                "part_key": normalized_part_key,
                "name": _canonical_part_name(normalized_part_key),
                "spec_name": row["spec_name"],
                "value": _display_component_value(
                    normalized_part_key,
                    row["spec_name"],
                    row["spec_value"],
                    row["component_name"],
                ),
                "slot": normalized_part_key,
                "brand_hint": row["inferred_brand_text"],
                "component_name": _display_component_value(
                    normalized_part_key,
                    row["spec_name"],
                    row["spec_value"],
                    row["component_name"],
                ),
                "offers_count": _metric_value(metric, default_metric, row, "offers_count", "offer_count") or 0,
                "reviews_count": _metric_value(metric, default_metric, row, "reviews_count", "review_count") or 0,
                "price_score": _metric_value(metric, default_metric, row, "price_score"),
                "quality_score": _metric_value(metric, default_metric, row, "quality_score"),
                "value_score": _metric_value(metric, default_metric, row, "value_score"),
            }
            raw_parts.append(part_row)
        parts = _compress_bike_parts(
            raw_parts,
            bike_type,
            part_metric_defaults,
            bike_name=bike["variant_name"],
            brand_name=bike["brand_name"],
        )
        for part_row in parts:
            parts_payload.append(
                {
                    "bike_variant_id": bike["bike_variant_id"],
                    "bike_name": bike["variant_name"],
                    "brand": bike["brand_name"],
                    **part_row,
                }
            )

        if component_ids:
            placeholders = ",".join("?" for _ in component_ids)
            offer_rows = conn.execute(
                f"""
                SELECT
                    os.component_catalog_id,
                    pt.part_key,
                    br.brand_name AS component_brand,
                    ss.source_code,
                    m.merchant_name,
                    os.offer_title,
                    os.offer_category,
                    os.price_value,
                    os.currency,
                    os.offer_url
                FROM offer_snapshot os
                LEFT JOIN component_catalog cc
                  ON cc.component_catalog_id = os.component_catalog_id
                LEFT JOIN part_taxonomy pt
                  ON pt.part_taxonomy_id = cc.part_taxonomy_id
                LEFT JOIN brand br
                  ON br.brand_id = cc.brand_id
                LEFT JOIN merchant m
                  ON m.merchant_id = os.merchant_id
                LEFT JOIN source_system ss
                  ON ss.source_id = os.source_id
                WHERE os.component_catalog_id IN ({placeholders})
                ORDER BY os.price_value
                """,
                component_ids,
            ).fetchall()
            for row in offer_rows:
                offers.append(
                    {
                        "part_key": row["part_key"],
                        "source": row["source_code"],
                        "merchant": row["merchant_name"],
                        "title": row["offer_title"],
                        "manufacturer": row["component_brand"],
                        "category": row["offer_category"],
                        "price_text": None,
                        "price_value": row["price_value"],
                        "currency": row["currency"],
                        "url": row["offer_url"],
                    }
                )

            review_rows = conn.execute(
                f"""
                SELECT
                    rt.component_catalog_id,
                    pt.part_key,
                    br.brand_name AS component_brand,
                    ss.source_code,
                    ra.title,
                    ra.summary,
                    ra.rating_value,
                    ra.review_url
                FROM review_target rt
                JOIN review_article ra
                  ON ra.review_article_id = rt.review_article_id
                LEFT JOIN component_catalog cc
                  ON cc.component_catalog_id = rt.component_catalog_id
                LEFT JOIN part_taxonomy pt
                  ON pt.part_taxonomy_id = cc.part_taxonomy_id
                LEFT JOIN brand br
                  ON br.brand_id = cc.brand_id
                LEFT JOIN source_system ss
                  ON ss.source_id = ra.source_id
                WHERE rt.component_catalog_id IN ({placeholders})
                ORDER BY ra.review_article_id
                """,
                component_ids,
            ).fetchall()
            for row in review_rows:
                reviews.append(
                    {
                        "part_key": row["part_key"],
                        "source": row["source_code"],
                        "title": row["title"],
                        "brand_hint": row["component_brand"],
                        "category": None,
                        "subtype": None,
                        "rating_text": None,
                        "rating_value": row["rating_value"],
                        "summary": row["summary"],
                        "url": row["review_url"],
                    }
                )

        bikes_payload.append(
            {
                "bike_name": bike["variant_name"],
                "brand": bike["brand_name"],
                "bike_type": bike_type,
                "template_type": template_type,
                "official_url": bike["official_url"],
                "description": bike["description"],
                "views": views,
                "parts": parts,
                "offers": offers,
                "reviews": reviews,
                "heatmap_metrics": {
                    "summary": {
                        "parts_count": len(parts),
                        "parts_with_offers": sum(1 for part in parts if part["offers_count"] > 0),
                        "parts_with_reviews": sum(1 for part in parts if part["reviews_count"] > 0),
                        "evidence_score": sum(
                            1
                            for part in parts
                            if (part["offers_count"] > 0)
                            or (part["reviews_count"] > 0)
                            or (part["price_score"] is not None)
                            or (part["quality_score"] is not None)
                        ),
                    },
                    "parts": [
                        {
                            "part_key": row["part_key"],
                            "name": row["part_name"],
                            "component_name": row["component_name"],
                            "offers_count": row["offer_count"],
                            "reviews_count": row["review_count"],
                            "price_score": row["price_score"],
                            "quality_score": row["quality_score"],
                            "value_score": row["value_score"],
                        }
                        for row in metric_rows
                    ],
                },
            }
        )

    component_rows = conn.execute(
        """
        SELECT
            cc.component_catalog_id,
            cc.component_name,
            cc.component_category,
            br.brand_name,
            cc.series_name,
            cc.model_code,
            cc.description,
            cms.offer_count,
            cms.review_count,
            cms.price_score,
            cms.quality_score,
            cms.value_score
        FROM component_catalog cc
        LEFT JOIN brand br
          ON br.brand_id = cc.brand_id
        LEFT JOIN component_metric_snapshot cms
          ON cms.component_catalog_id = cc.component_catalog_id
         AND cms.snapshot_date = ?
        ORDER BY br.brand_name, cc.component_name
        """,
        (component_snapshot_date,),
    ).fetchall()
    components_payload = []
    for row in component_rows:
        view_rows = conn.execute(
            """
            SELECT cm.view_type, ma.original_url, ma.local_path
            FROM component_media cm
            JOIN media_asset ma
              ON ma.media_id = cm.media_id
            WHERE cm.component_catalog_id = ?
            ORDER BY cm.sort_order
            """,
            (row["component_catalog_id"],),
        ).fetchall()
        spec_rows = conn.execute(
            """
            SELECT spec_name, spec_value
            FROM component_catalog_spec
            WHERE component_catalog_id = ?
            ORDER BY spec_name
            """,
            (row["component_catalog_id"],),
        ).fetchall()
        offer_rows = conn.execute(
            """
            SELECT
                ss.source_code,
                m.merchant_name,
                os.offer_title,
                os.offer_category,
                os.price_value,
                os.currency,
                os.offer_url
            FROM offer_snapshot os
            LEFT JOIN merchant m
              ON m.merchant_id = os.merchant_id
            LEFT JOIN source_system ss
              ON ss.source_id = os.source_id
            WHERE os.component_catalog_id = ?
            ORDER BY os.price_value
            """,
            (row["component_catalog_id"],),
        ).fetchall()
        review_rows = conn.execute(
            """
            SELECT
                ss.source_code,
                ra.title,
                ra.summary,
                ra.rating_value,
                ra.review_url
            FROM review_target rt
            JOIN review_article ra
              ON ra.review_article_id = rt.review_article_id
            LEFT JOIN source_system ss
              ON ss.source_id = ra.source_id
            WHERE rt.component_catalog_id = ?
            ORDER BY ra.review_article_id
            """,
            (row["component_catalog_id"],),
        ).fetchall()
        components_payload.append(
            {
                "component_name": row["component_name"],
                "brand": row["brand_name"],
                "views": _row_to_view_map(view_rows),
                "parts": [
                    {"name": spec["spec_name"], "value": spec["spec_value"]}
                    for spec in spec_rows
                ],
                "offers": [
                    {
                        "source": offer["source_code"],
                        "merchant": offer["merchant_name"],
                        "title": offer["offer_title"],
                        "category": offer["offer_category"],
                        "price_text": None,
                        "price_value": offer["price_value"],
                        "currency": offer["currency"],
                        "url": offer["offer_url"],
                    }
                    for offer in offer_rows
                ],
                "reviews": [
                    {
                        "source": review["source_code"],
                        "title": review["title"],
                        "summary": review["summary"],
                        "rating_text": None,
                        "rating_value": review["rating_value"],
                        "url": review["review_url"],
                    }
                    for review in review_rows
                ],
                "heatmap_metrics": {
                    "summary": {
                        "offers_count": row["offer_count"] or 0,
                        "reviews_count": row["review_count"] or 0,
                        "price_score": row["price_score"],
                        "quality_score": row["quality_score"],
                        "value_score": row["value_score"],
                    }
                },
            }
        )

    (export_dir / "website_bikes_api.json").write_text(
        json.dumps(bikes_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (export_dir / "website_parts_api.json").write_text(
        json.dumps(parts_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (export_dir / "website_components_api.json").write_text(
        json.dumps(components_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    conn.close()
    return {
        "website_bikes_api": len(bikes_payload),
        "website_parts_api": len(parts_payload),
        "website_components_api": len(components_payload),
    }
