from __future__ import annotations

import json
import re
from pathlib import Path

from bike_data_platform.storage import connect_db, initialize_schema, read_jsonl
from bike_data_platform.transformers.warehouse import parse_price_value, parse_rating_value


COMPONENT_BRANDS = [
    "shimano",
    "sram",
    "giant",
    "merida",
    "brompton",
    "dahon",
    "oyama",
    "fnhon",
    "rock shox",
    "rockshox",
    "fox",
    "trp",
    "litepro",
    "schwalbe",
    "continental",
    "maxxis",
    "dt swiss",
    "race face",
    "oneup",
    "renthal",
    "ks",
    "sdg",
    "e thirteen",
    "ethirteen",
    "mrp",
    "cane creek",
    "magura",
    "marzocchi",
    "syncros",
    "bontrager",
    "wtb",
    "vittoria",
    "pirelli",
    "deity",
    "burgtec",
    "crankbrothers",
    "industry nine",
    "bosch",
]

COMPONENT_HINTS = [
    "frame",
    "fork",
    "shock",
    "derailleur",
    "brake",
    "cassette",
    "chain",
    "crank",
    "wheel",
    "rim",
    "hub",
    "tyre",
    "tire",
    "groupset",
    "battery",
    "motor",
    "saddle",
    "seatpost",
    "handlebar",
    "shifter",
    "lever",
    "rotor",
    "pedal",
    "dropper",
    "grip",
    "stem",
    "guide",
    "bash",
    "linkage",
    "travel",
    "lockout",
]

SHORT_COMPONENT_TOKENS = {
    "gx",
    "xo",
    "xx",
    "xx1",
    "sx",
    "nx",
    "xt",
    "xtr",
    "slx",
    "axs",
    "sid",
    "zeb",
    "g2",
    "db8",
}

NON_COMPONENT_TERMS = [
    "frame size",
    "head tube",
    "seat tube",
    "seat angle",
    "head angle",
    "wheel base",
    "wheelbase",
    "stack",
    "reach",
    "top tube",
    "stand over",
    "fork length",
    "chain stay",
    "chainstay",
    "color",
    "sizes",
    "weight",
]

NON_BIKE_PRODUCT_KEYWORDS = [
    "jersey",
    "bibshort",
    "sock",
    "helmet",
    "shoe",
    "cockpit",
    "extension",
    "glove",
    "jacket",
    "bottle",
    "bag",
    "pump",
    "tool",
]


def normalize_component_key(name: str, value: str) -> str:
    text = f"{name} {value}".lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")[:120]


def infer_brand(value: str) -> str | None:
    lower = value.lower()
    for brand in COMPONENT_BRANDS:
        if brand in lower:
            return brand.title().replace("Rock Shox", "RockShox")
    return None


def is_component_like(name: str, value: str) -> bool:
    lower = f"{name} {value}".lower()
    if any(term in lower for term in NON_COMPONENT_TERMS):
        return False
    return any(term in lower for term in COMPONENT_HINTS)


def is_valid_official_bike_row(row: dict) -> bool:
    brand = (row.get("brand") or "").lower()
    bike_name = (row.get("bike_name") or "").strip()
    bike_url = (row.get("bike_url") or row.get("source_id") or "").strip()
    description = (row.get("description") or "").lower()
    specs = row.get("specs") or []
    components = row.get("components") or []

    if not bike_name or not bike_url:
        return False
    if len(bike_url) > 500 or any(token in bike_url for token in ['"', "<", "Request-URI Too Long"]):
        return False

    lower_name = bike_name.lower()
    lower_url = bike_url.lower()
    if bike_name in {"Not Found", "Request-URI Too Long"}:
        return False

    if brand == "trek":
        if "/p/" not in lower_url:
            return False
        if lower_name.startswith("shop ") or "bike finder" in lower_name or "buyer" in lower_name:
            return False
    elif brand == "canyon":
        if any(token in lower_url for token in ("/gear/", "/apparel/", "/outlet/", "/collections/")):
            return False
        if any(token in lower_name for token in NON_BIKE_PRODUCT_KEYWORDS):
            return False
    elif brand == "cannondale":
        if not re.search(
            r"/en(?:-us)?/bikes/(road|mountain)/(race|endurance|gravel|cyclocross|trail-bikes|cross-country-bikes|downhill-bikes)/[a-z0-9\-]+/[a-z0-9\-]+(?:/\d{4})?(?:\?.*)?$|/en(?:-us)?/bikes/electric/e-mountain/[a-z0-9\-]+/[a-z0-9\-]+(?:/\d{4})?(?:\?.*)?$",
            lower_url,
        ):
            return False
        if "resultresults" in description:
            return False
        mtb_signal = any(
            token in f"{lower_name} {description} {lower_url}"
            for token in ("habit", "scalpel", "jekyll", "moterra", "trail", "mountain", "f-si")
        )
        if len(specs) < (8 if mtb_signal else 10) and len(components) < (2 if mtb_signal else 3):
            return False
    return True


def latest_files_by_suffix(raw_dir: Path, suffixes: tuple[str, ...], latest_only: bool = True) -> list[Path]:
    groups: dict[str, Path] = {}
    matched: list[Path] = []
    for path in sorted(raw_dir.glob("*.jsonl")):
        stem = path.stem
        source_key = stem.split("_", 1)[1] if "_" in stem else stem
        if source_key.endswith(suffixes):
            if latest_only:
                groups[source_key] = path
            else:
                matched.append(path)
    if not latest_only:
        return matched
    return sorted(groups.values())


def _match_component_to_component_offer(component_name: str, component_value: str, row: dict) -> bool:
    if not is_component_like(component_name, component_value):
        return False
    offer_text = f"{row.get('name', '')} {row.get('category', '')} {row.get('manufacturer', '')}".lower()
    if "apparel" in offer_text:
        return False
    brand = infer_brand(component_value) or infer_brand(component_name)
    name_tokens = _component_tokens(component_name)
    value_tokens = _component_tokens(component_value)
    if brand and brand.lower() not in offer_text:
        return False
    return bool(name_tokens) and any(token in offer_text for token in name_tokens) and (
        not value_tokens or any(token in offer_text for token in value_tokens)
    )


def _match_component_to_review(component_name: str, component_value: str, row: dict) -> bool:
    if not is_component_like(component_name, component_value):
        return False
    review_text = f"{row.get('title', '')} {row.get('summary', '')} {row.get('brand_hint', '')}".lower()
    brand = infer_brand(component_value) or infer_brand(component_name)
    if brand and brand.lower() not in review_text:
        return False
    name_tokens = _component_tokens(component_name)
    value_tokens = _component_tokens(component_value)
    return bool(name_tokens) and any(token in review_text for token in name_tokens) and (
        not value_tokens or any(token in review_text for token in value_tokens)
    )


def _component_tokens(*parts: str) -> list[str]:
    tokens: list[str] = []
    for part in parts:
        for token in re.split(r"[^a-z0-9]+", part.lower()):
            if len(token) >= 4 or token in SHORT_COMPONENT_TOKENS or (len(token) >= 2 and any(ch.isdigit() for ch in token)):
                tokens.append(token)
    seen = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
    return seen


def _official_component_match_tokens(component_name: str) -> list[str]:
    stopwords = {"shimano", "sram", "series", "component", "components", "product", "detail", "page"}
    tokens = _component_tokens(component_name)
    return [token for token in tokens if token not in stopwords]


def build_brand_warehouse(raw_crawl_dir: Path, db_path: Path, schema_path: Path) -> dict:
    conn = connect_db(db_path)
    initialize_schema(conn, schema_path)
    for table in [
        "official_bike_rows",
        "official_bike_components",
        "official_bike_specs",
        "official_bikes",
        "official_component_rows",
        "official_component_specs",
        "official_components",
        "component_market_offers",
        "component_quality_reviews",
    ]:
        conn.execute(f"DELETE FROM {table}")

    inserted = {
        "official_bikes": 0,
        "official_bike_components": 0,
        "official_bike_specs": 0,
        "component_market_offers": 0,
        "component_quality_reviews": 0,
        "official_bike_rows": 0,
        "official_components": 0,
        "official_component_specs": 0,
        "official_component_rows": 0,
    }

    # Official browser crawls are often run brand by brand, so keep all matching files
    # instead of only the latest one; downstream INSERT OR REPLACE handles duplicates.
    official_files = latest_files_by_suffix(
        raw_crawl_dir,
        ("official_sites", "official_sites_browser"),
        latest_only=False,
    )
    market_component_rows = []
    market_review_rows = []
    for path in latest_files_by_suffix(raw_crawl_dir, ("bike_components", "bikeradar")):
        for row in read_jsonl(path):
            if row.get("entity") == "component":
                market_component_rows.append(row)
            elif row.get("entity") == "review":
                market_review_rows.append(row)

    for path in official_files:
        for row in read_jsonl(path):
            if row.get("entity") != "official_bike":
                if row.get("entity") != "official_component":
                    continue
                payload_json = json.dumps(row.get("payload", {}), ensure_ascii=False)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO official_components(
                        source, source_id, brand, component_name, component_url, component_category,
                        price_text, description, image_url, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source"),
                        row.get("source_id"),
                        row.get("brand"),
                        row.get("component_name"),
                        row.get("component_url"),
                        row.get("component_category"),
                        row.get("price_text"),
                        row.get("description"),
                        row.get("side_view_url") or row.get("front_view_url"),
                        payload_json,
                    ),
                )
                inserted["official_components"] += 1

                specs = row.get("specs", [])
                for idx, spec in enumerate(specs, start=1):
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO official_component_specs(
                            component_source, component_source_id, spec_order, spec_name, spec_value
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            row.get("source"),
                            row.get("source_id"),
                            idx,
                            spec.get("name"),
                            spec.get("value"),
                        ),
                    )
                    inserted["official_component_specs"] += 1

                component_name = row.get("component_name", "")
                component_category = row.get("component_category", "") or ""
                tokens = _official_component_match_tokens(component_name)
                brand_name = (row.get("brand") or "").lower()
                offer_matches = []
                review_matches = []
                for offer in market_component_rows:
                    offer_text = f"{offer.get('name', '')} {offer.get('category', '')} {offer.get('manufacturer', '')}".lower()
                    if brand_name and brand_name not in offer_text:
                        continue
                    if not tokens or sum(1 for token in tokens if token in offer_text) < 1:
                        continue
                    if "apparel" in offer_text:
                        continue
                    price_value, currency = parse_price_value(offer.get("price_text"))
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO component_market_offers(
                            component_key, matched_component_name, offer_source, offer_source_id, offer_title,
                            manufacturer, category, price_text, price_value, currency, url, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            normalize_component_key(component_name, component_category),
                            component_name,
                            offer.get("source"),
                            offer.get("source_id"),
                            offer.get("name"),
                            offer.get("manufacturer"),
                            offer.get("category"),
                            offer.get("price_text"),
                            price_value,
                            currency,
                            offer.get("url"),
                            json.dumps(offer.get("payload", {}), ensure_ascii=False),
                        ),
                    )
                    inserted["component_market_offers"] += 1
                    offer_matches.append(
                        {
                            "source": offer.get("source"),
                            "title": offer.get("name"),
                            "price_text": offer.get("price_text"),
                            "manufacturer": offer.get("manufacturer"),
                            "url": offer.get("url"),
                        }
                    )

                for review in market_review_rows:
                    review_text = f"{review.get('title', '')} {review.get('summary', '')} {review.get('brand_hint', '')}".lower()
                    if brand_name and brand_name not in review_text:
                        continue
                    if not tokens or sum(1 for token in tokens if token in review_text) < 1:
                        continue
                    rating_value, _ = parse_rating_value(review.get("rating_text"))
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO component_quality_reviews(
                            component_key, review_source, review_source_id, review_title, brand_hint,
                            category, subtype, rating_text, rating_value, summary, url, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            normalize_component_key(component_name, component_category),
                            review.get("source"),
                            review.get("source_id"),
                            review.get("title"),
                            review.get("brand_hint"),
                            review.get("category"),
                            review.get("subtype"),
                            review.get("rating_text"),
                            rating_value,
                            review.get("summary"),
                            review.get("url"),
                            json.dumps(review.get("payload", {}), ensure_ascii=False),
                        ),
                    )
                    inserted["component_quality_reviews"] += 1
                    review_matches.append(
                        {
                            "source": review.get("source"),
                            "title": review.get("title"),
                            "brand_hint": review.get("brand_hint"),
                            "summary": review.get("summary"),
                            "url": review.get("url"),
                        }
                    )

                conn.execute(
                    """
                    INSERT OR REPLACE INTO official_component_rows(
                        source, source_id, brand, component_name, component_url, component_category,
                        image_url, specs_json, market_offers_json, quality_reviews_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source"),
                        row.get("source_id"),
                        row.get("brand"),
                        component_name,
                        row.get("component_url"),
                        component_category,
                        row.get("side_view_url") or row.get("front_view_url"),
                        json.dumps(specs, ensure_ascii=False),
                        json.dumps(offer_matches, ensure_ascii=False),
                        json.dumps(review_matches, ensure_ascii=False),
                    ),
                )
                inserted["official_component_rows"] += 1
                continue
            if not is_valid_official_bike_row(row):
                continue
            payload_json = json.dumps(row.get("payload", {}), ensure_ascii=False)
            conn.execute(
                """
                INSERT OR REPLACE INTO official_bikes(source, source_id, brand, bike_name, bike_url,
                price_text, description, front_view_url, side_view_url, rear_view_url, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("source"),
                    row.get("source_id"),
                    row.get("brand"),
                    row.get("bike_name"),
                    row.get("bike_url"),
                    row.get("price_text"),
                    row.get("description"),
                    row.get("front_view_url"),
                    row.get("side_view_url"),
                    row.get("rear_view_url"),
                    payload_json,
                ),
            )
            inserted["official_bikes"] += 1

            for idx, spec in enumerate(row.get("specs", []), start=1):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO official_bike_specs(
                        bike_source, bike_source_id, spec_order, spec_name, spec_value
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source"),
                        row.get("source_id"),
                        idx,
                        spec.get("name"),
                        spec.get("value"),
                    ),
                )
                inserted["official_bike_specs"] += 1

            component_summaries = []
            for idx, component in enumerate(row.get("components", []), start=1):
                component_name = component.get("name", "")
                component_value = component.get("value", "")
                if not is_component_like(component_name, component_value):
                    continue
                component_key = normalize_component_key(component_name, component_value)
                inferred_brand = infer_brand(component_value)
                offer_matches = []
                review_matches = []
                conn.execute(
                    """
                    INSERT OR REPLACE INTO official_bike_components(
                        bike_source, bike_source_id, component_order, component_name, component_value,
                        normalized_component_key, inferred_brand
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("source"),
                        row.get("source_id"),
                        idx,
                        component_name,
                        component_value,
                        component_key,
                        inferred_brand,
                    ),
                )
                inserted["official_bike_components"] += 1

                for offer in market_component_rows:
                    if not _match_component_to_component_offer(component_name, component_value, offer):
                        continue
                    price_value, currency = parse_price_value(offer.get("price_text"))
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO component_market_offers(
                            component_key, matched_component_name, offer_source, offer_source_id, offer_title,
                            manufacturer, category, price_text, price_value, currency, url, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            component_key,
                            f"{component_name}: {component_value}",
                            offer.get("source"),
                            offer.get("source_id"),
                            offer.get("name"),
                            offer.get("manufacturer"),
                            offer.get("category"),
                            offer.get("price_text"),
                            price_value,
                            currency,
                            offer.get("url"),
                            json.dumps(offer.get("payload", {}), ensure_ascii=False),
                        ),
                    )
                    inserted["component_market_offers"] += 1
                    offer_matches.append(
                        {
                            "source": offer.get("source"),
                            "title": offer.get("name"),
                            "price_text": offer.get("price_text"),
                            "manufacturer": offer.get("manufacturer"),
                            "url": offer.get("url"),
                        }
                    )

                for review in market_review_rows:
                    if not _match_component_to_review(component_name, component_value, review):
                        continue
                    rating_value, _ = parse_rating_value(review.get("rating_text"))
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO component_quality_reviews(
                            component_key, review_source, review_source_id, review_title, brand_hint,
                            category, subtype, rating_text, rating_value, summary, url, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            component_key,
                            review.get("source"),
                            review.get("source_id"),
                            review.get("title"),
                            review.get("brand_hint"),
                            review.get("category"),
                            review.get("subtype"),
                            review.get("rating_text"),
                            rating_value,
                            review.get("summary"),
                            review.get("url"),
                            json.dumps(review.get("payload", {}), ensure_ascii=False),
                        ),
                    )
                    inserted["component_quality_reviews"] += 1
                    review_matches.append(
                        {
                            "source": review.get("source"),
                            "title": review.get("title"),
                            "brand_hint": review.get("brand_hint"),
                            "summary": review.get("summary"),
                            "url": review.get("url"),
                        }
                    )

                component_summaries.append(
                    {
                        "component_key": component_key,
                        "component_name": component_name,
                        "component_value": component_value,
                        "market_offers": offer_matches,
                        "quality_reviews": review_matches,
                    }
                )

            conn.execute(
                """
                INSERT OR REPLACE INTO official_bike_rows(
                    source, source_id, brand, bike_name, bike_url, front_view_url, side_view_url,
                    rear_view_url, component_table_json, price_quality_summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("source"),
                    row.get("source_id"),
                    row.get("brand"),
                    row.get("bike_name"),
                    row.get("bike_url"),
                    row.get("front_view_url"),
                    row.get("side_view_url"),
                    row.get("rear_view_url"),
                    json.dumps(row.get("components", []), ensure_ascii=False),
                    json.dumps(component_summaries, ensure_ascii=False),
                ),
            )
            inserted["official_bike_rows"] += 1

    conn.commit()
    summary = {}
    for table in [
        "official_bikes",
        "official_bike_components",
        "official_bike_specs",
        "component_market_offers",
        "component_quality_reviews",
        "official_bike_rows",
        "official_components",
        "official_component_specs",
        "official_component_rows",
    ]:
        summary[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return {"inserted": inserted, "summary": summary}
