from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from PIL import Image

from bike_data_platform.storage import connect_db, initialize_schema
from bike_data_platform.transformers.brand_warehouse import infer_brand, normalize_component_key
from bike_data_platform.transformers.warehouse import parse_price_value, parse_rating_value


PART_TAXONOMY_SEED = [
    {"part_key": "frame", "part_name": "Frame", "parent": None, "level": 1, "slot": "frame"},
    {"part_key": "fork", "part_name": "Fork", "parent": None, "level": 1, "slot": "fork"},
    {"part_key": "shock", "part_name": "Shock", "parent": None, "level": 1, "slot": "shock"},
    {"part_key": "handlebar", "part_name": "Handlebar", "parent": None, "level": 1, "slot": "handlebar"},
    {"part_key": "saddle", "part_name": "Saddle", "parent": None, "level": 1, "slot": "saddle"},
    {"part_key": "seatpost", "part_name": "Seatpost", "parent": None, "level": 1, "slot": "seatpost"},
    {"part_key": "wheel", "part_name": "Wheel", "parent": None, "level": 1, "slot": "wheel"},
    {"part_key": "front_wheel", "part_name": "Front Wheel", "parent": "wheel", "level": 2, "slot": "wheel"},
    {"part_key": "rear_wheel", "part_name": "Rear Wheel", "parent": "wheel", "level": 2, "slot": "wheel"},
    {"part_key": "tyre", "part_name": "Tyre", "parent": None, "level": 1, "slot": "tyre"},
    {"part_key": "brake", "part_name": "Brake", "parent": None, "level": 1, "slot": "brake"},
    {"part_key": "drivetrain", "part_name": "Drivetrain", "parent": None, "level": 1, "slot": "drivetrain"},
    {"part_key": "shifter", "part_name": "Shifter", "parent": "drivetrain", "level": 2, "slot": "shifter"},
    {"part_key": "derailleur", "part_name": "Derailleur", "parent": "drivetrain", "level": 2, "slot": "derailleur"},
    {"part_key": "cassette", "part_name": "Cassette", "parent": "drivetrain", "level": 2, "slot": "cassette"},
    {"part_key": "chain", "part_name": "Chain", "parent": "drivetrain", "level": 2, "slot": "chain"},
    {"part_key": "crankset", "part_name": "Crankset", "parent": "drivetrain", "level": 2, "slot": "crankset"},
    {"part_key": "pedal", "part_name": "Pedal", "parent": None, "level": 1, "slot": "pedal"},
    {"part_key": "motor", "part_name": "Motor", "parent": None, "level": 1, "slot": "motor"},
    {"part_key": "battery", "part_name": "Battery", "parent": None, "level": 1, "slot": "battery"},
    {"part_key": "groupset", "part_name": "Groupset", "parent": "drivetrain", "level": 2, "slot": "drivetrain"},
    {"part_key": "component", "part_name": "Component", "parent": None, "level": 1, "slot": "component"},
    {"part_key": "bicycle", "part_name": "Bicycle", "parent": None, "level": 1, "slot": "bicycle"},
]


PART_SLOT_RULES = {
    "frame": ["frame"],
    "fork": ["fork"],
    "shock": ["shock", "damper", "linkage", "travel", "lockout"],
    "handlebar": ["handlebar", "bar", "stem", "grip"],
    "saddle": ["saddle"],
    "seatpost": ["seatpost", "seat post", "dropper", "dropper post"],
    "shifter": ["shifter", "shift lever", "lever"],
    "brake": ["brake", "rotor", "caliper"],
    "derailleur": ["derailleur"],
    "cassette": ["cassette", "freewheel"],
    "chain": ["chain"],
    "crankset": ["crank", "chainwheel", "chainring", "bottom bracket", "bash", "guide"],
    "wheel": ["wheel", "rim", "hub", "spoke"],
    "tyre": ["tyre", "tire"],
    "motor": ["motor"],
    "battery": ["battery"],
    "pedal": ["pedal"],
    "groupset": ["groupset"],
}


KNOWN_DATASETS = {
    "delftbikes": "DelftBikes",
    "bbbicycles": "BBBicycles",
    "geobiked": "GeoBIKED",
    "side_view_annotation_candidates": "Side View Annotation Candidates",
    "cvat_side_view_dataset": "CVAT Side View Dataset",
    "white_background_silhouettes": "White Background Silhouettes",
}


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def load_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def safe_json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


def file_sha256(path: Path) -> str | None:
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def normalize_slug(value: str) -> str:
    value = (value or "").strip().lower()
    chars: list[str] = []
    prev_dash = False
    for char in value:
        if char.isalnum():
            chars.append(char)
            prev_dash = False
            continue
        if not prev_dash:
            chars.append("-")
            prev_dash = True
    return "".join(chars).strip("-") or "unknown"


def guess_source_type(source_code: str) -> str:
    lower = source_code.lower()
    if lower.startswith("official_"):
        return "official_site"
    if lower in {"bike-components", "bike_components", "bikeradar"}:
        return "market_site" if "component" in lower else "review_site"
    if lower in {"bike_index", "wikimedia", "wikimedia_commons"}:
        return "open_api"
    if lower in {"delftbikes", "bbbicycles", "geobiked"}:
        return "dataset"
    if "annotation" in lower or "cvat" in lower:
        return "annotation"
    return "external"


def infer_part_key(*texts: str) -> str:
    lower = " ".join(texts).lower()
    for part_key, hints in PART_SLOT_RULES.items():
        if any(hint in lower for hint in hints):
            return part_key
    return "component"


def guess_family_name(brand_name: str, bike_name: str) -> str:
    cleaned = (bike_name or "").strip()
    if not cleaned:
        return "Unknown Family"
    lower_brand = (brand_name or "").strip().lower()
    if lower_brand and cleaned.lower().startswith(lower_brand + " "):
        cleaned = cleaned[len(brand_name) :].strip()
    tokens = [token for token in cleaned.replace("/", " ").split() if token]
    if not tokens:
        return bike_name.strip()
    return tokens[0]


def guess_model_name(brand_name: str, bike_name: str) -> str:
    cleaned = (bike_name or "").strip()
    if not cleaned:
        return "Unknown Model"
    lower_brand = (brand_name or "").strip().lower()
    if lower_brand and cleaned.lower().startswith(lower_brand + " "):
        cleaned = cleaned[len(brand_name) :].strip()
    return cleaned


def choose_text(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def choose_number(*values: object) -> float | None:
    for value in values:
        if value in (None, "", "None"):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


class UnifiedWarehouseBuilder:
    def __init__(self, project_root: Path, conn: sqlite3.Connection) -> None:
        self.project_root = project_root
        self.conn = conn
        self.source_cache: dict[str, int] = {}
        self.brand_cache: dict[str, int] = {}
        self.part_cache: dict[str, int] = {}
        self.dataset_cache: dict[str, int] = {}
        self.dataset_version_cache: dict[tuple[int, str], int] = {}
        self.merchant_cache: dict[str, int] = {}
        self.media_cache: dict[tuple[str | None, str | None], int] = {}
        self.family_cache: dict[tuple[int, str], int] = {}
        self.model_cache: dict[tuple[int, str, int | None], int] = {}
        self.variant_source_cache: dict[tuple[str, str], int] = {}
        self.component_cache: dict[str, int] = {}
        self.component_key_map: dict[str, int] = {}
        self.image_cache: dict[str, int] = {}
        self.annotation_task_cache: dict[str, int] = {}
        self.bike_instance_cache: dict[int, int] = {}
        self.bike_alias_cache: set[tuple[int, str, str]] = set()
        self.component_alias_cache: set[tuple[int, str, str]] = set()
        self.summary: dict[str, int] = defaultdict(int)

    def ensure_source(self, source_code: str, source_name: str | None = None, source_type: str | None = None) -> int:
        source_code = normalize_slug(source_code).replace("-", "_")
        if source_code in self.source_cache:
            return self.source_cache[source_code]
        row = self.conn.execute(
            "SELECT source_id FROM source_system WHERE source_code = ?",
            (source_code,),
        ).fetchone()
        if row:
            self.source_cache[source_code] = int(row[0])
            return int(row[0])
        self.conn.execute(
            """
            INSERT INTO source_system(source_code, source_name, source_type)
            VALUES (?, ?, ?)
            """,
            (
                source_code,
                source_name or source_code.replace("_", " ").title(),
                source_type or guess_source_type(source_code),
            ),
        )
        source_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.source_cache[source_code] = source_id
        self.summary["source_system"] += 1
        return source_id

    def ensure_ingestion_run(
        self,
        source_code: str,
        pipeline_stage: str,
        started_at: str,
        status: str,
        raw_path: str | None = None,
        record_count: int = 0,
        note: str | None = None,
    ) -> int:
        source_id = self.ensure_source(source_code)
        self.conn.execute(
            """
            INSERT INTO ingestion_run(source_id, pipeline_stage, started_at, finished_at, status, raw_path, record_count, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source_id, pipeline_stage, started_at, started_at, status, raw_path, record_count, note),
        )
        self.summary["ingestion_run"] += 1
        return int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    def ensure_source_record(
        self,
        run_id: int,
        source_entity_type: str,
        source_entity_id: str,
        raw_payload: dict | None = None,
        canonical_table: str | None = None,
        canonical_id: int | None = None,
    ) -> int:
        row = self.conn.execute(
            """
            SELECT source_record_id FROM source_record
            WHERE run_id = ? AND source_entity_type = ? AND source_entity_id = ?
            """,
            (run_id, source_entity_type, source_entity_id),
        ).fetchone()
        payload_text = safe_json_text(raw_payload or {})
        if row:
            source_record_id = int(row[0])
            self.conn.execute(
                """
                UPDATE source_record
                SET canonical_table = COALESCE(canonical_table, ?),
                    canonical_id = COALESCE(canonical_id, ?),
                    raw_payload_json = ?
                WHERE source_record_id = ?
                """,
                (canonical_table, canonical_id, payload_text, source_record_id),
            )
            return source_record_id
        self.conn.execute(
            """
            INSERT INTO source_record(
                run_id, source_entity_type, source_entity_id, canonical_table, canonical_id, raw_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, source_entity_type, source_entity_id, canonical_table, canonical_id, payload_text),
        )
        self.summary["source_record"] += 1
        return int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    def ensure_dataset(self, dataset_code: str, dataset_name: str | None = None, source_code: str | None = None) -> int:
        dataset_code = normalize_slug(dataset_code).replace("-", "_")
        if dataset_code in self.dataset_cache:
            return self.dataset_cache[dataset_code]
        row = self.conn.execute(
            "SELECT dataset_id FROM dataset WHERE dataset_code = ?",
            (dataset_code,),
        ).fetchone()
        if row:
            self.dataset_cache[dataset_code] = int(row[0])
            return int(row[0])
        source_id = self.ensure_source(source_code or dataset_code) if source_code else None
        self.conn.execute(
            """
            INSERT INTO dataset(source_id, dataset_code, dataset_name)
            VALUES (?, ?, ?)
            """,
            (
                source_id,
                dataset_code,
                dataset_name or KNOWN_DATASETS.get(dataset_code, dataset_code.replace("_", " ").title()),
            ),
        )
        dataset_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.dataset_cache[dataset_code] = dataset_id
        self.summary["dataset"] += 1
        return dataset_id

    def ensure_dataset_version(self, dataset_code: str, version_tag: str, note: str | None = None) -> int:
        dataset_id = self.ensure_dataset(dataset_code)
        key = (dataset_id, version_tag)
        if key in self.dataset_version_cache:
            return self.dataset_version_cache[key]
        row = self.conn.execute(
            "SELECT dataset_version_id FROM dataset_version WHERE dataset_id = ? AND version_tag = ?",
            (dataset_id, version_tag),
        ).fetchone()
        if row:
            self.dataset_version_cache[key] = int(row[0])
            return int(row[0])
        self.conn.execute(
            """
            INSERT INTO dataset_version(dataset_id, version_tag, note)
            VALUES (?, ?, ?)
            """,
            (dataset_id, version_tag, note),
        )
        dataset_version_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.dataset_version_cache[key] = dataset_version_id
        self.summary["dataset_version"] += 1
        return dataset_version_id

    def seed_part_taxonomy(self) -> None:
        for item in PART_TAXONOMY_SEED:
            self.ensure_part_taxonomy(
                part_key=item["part_key"],
                part_name=item["part_name"],
                parent_key=item["parent"],
                part_level=item["level"],
                visualization_slot=item["slot"],
            )

    def ensure_part_taxonomy(
        self,
        part_key: str,
        part_name: str | None = None,
        parent_key: str | None = None,
        part_level: int = 1,
        visualization_slot: str | None = None,
    ) -> int:
        part_key = normalize_slug(part_key).replace("-", "_")
        if part_key in self.part_cache:
            return self.part_cache[part_key]
        row = self.conn.execute(
            "SELECT part_taxonomy_id FROM part_taxonomy WHERE part_key = ?",
            (part_key,),
        ).fetchone()
        if row:
            self.part_cache[part_key] = int(row[0])
            return int(row[0])
        parent_id = None
        if parent_key:
            parent_id = self.ensure_part_taxonomy(parent_key, parent_key.replace("_", " ").title())
        self.conn.execute(
            """
            INSERT INTO part_taxonomy(parent_part_taxonomy_id, part_key, part_name, part_level, visualization_slot)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                parent_id,
                part_key,
                part_name or part_key.replace("_", " ").title(),
                part_level,
                visualization_slot or part_key,
            ),
        )
        part_taxonomy_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.part_cache[part_key] = part_taxonomy_id
        self.summary["part_taxonomy"] += 1
        return part_taxonomy_id

    def ensure_brand(self, brand_name: str | None) -> int | None:
        brand_name = choose_text(brand_name)
        if not brand_name:
            return None
        key = brand_name.lower()
        slug = normalize_slug(brand_name)
        if key in self.brand_cache:
            return self.brand_cache[key]
        row = self.conn.execute(
            "SELECT brand_id, brand_name FROM brand WHERE lower(brand_name) = ? OR brand_slug = ?",
            (key, slug),
        ).fetchone()
        if row:
            self.brand_cache[key] = int(row[0])
            self.brand_cache[str(row["brand_name"]).lower()] = int(row[0])
            return int(row[0])
        self.conn.execute(
            """
            INSERT INTO brand(brand_name, brand_slug)
            VALUES (?, ?)
            """,
            (brand_name, slug),
        )
        brand_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.brand_cache[key] = brand_id
        self.summary["brand"] += 1
        return brand_id

    def ensure_merchant(self, merchant_name: str | None) -> int | None:
        merchant_name = choose_text(merchant_name)
        if not merchant_name:
            return None
        key = merchant_name.lower()
        if key in self.merchant_cache:
            return self.merchant_cache[key]
        row = self.conn.execute(
            "SELECT merchant_id FROM merchant WHERE lower(merchant_name) = ?",
            (key,),
        ).fetchone()
        if row:
            self.merchant_cache[key] = int(row[0])
            return int(row[0])
        self.conn.execute(
            """
            INSERT INTO merchant(merchant_name)
            VALUES (?)
            """,
            (merchant_name,),
        )
        merchant_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.merchant_cache[key] = merchant_id
        self.summary["merchant"] += 1
        return merchant_id

    def ensure_bike_variant_alias(
        self,
        bike_variant_id: int,
        alias_text: str | None,
        alias_type: str = "name",
        source_code: str | None = None,
        source_entity_id: str | None = None,
    ) -> None:
        alias_text = choose_text(alias_text)
        if not alias_text:
            return
        alias_slug = normalize_slug(alias_text)
        cache_key = (bike_variant_id, alias_slug, alias_type)
        if cache_key in self.bike_alias_cache:
            return
        source_id = self.ensure_source(source_code) if source_code else None
        self.conn.execute(
            """
            INSERT OR IGNORE INTO bike_variant_alias(
                bike_variant_id, alias_text, alias_slug, alias_type, source_id, source_entity_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (bike_variant_id, alias_text, alias_slug, alias_type, source_id, source_entity_id),
        )
        if self.conn.execute("SELECT changes()").fetchone()[0]:
            self.summary["bike_variant_alias"] += 1
        self.bike_alias_cache.add(cache_key)

    def ensure_component_catalog_alias(
        self,
        component_catalog_id: int,
        alias_text: str | None,
        alias_type: str = "name",
        source_code: str | None = None,
        source_entity_id: str | None = None,
    ) -> None:
        alias_text = choose_text(alias_text)
        if not alias_text:
            return
        alias_slug = normalize_slug(alias_text)
        cache_key = (component_catalog_id, alias_slug, alias_type)
        if cache_key in self.component_alias_cache:
            return
        source_id = self.ensure_source(source_code) if source_code else None
        self.conn.execute(
            """
            INSERT OR IGNORE INTO component_catalog_alias(
                component_catalog_id, alias_text, alias_slug, alias_type, source_id, source_entity_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (component_catalog_id, alias_text, alias_slug, alias_type, source_id, source_entity_id),
        )
        if self.conn.execute("SELECT changes()").fetchone()[0]:
            self.summary["component_catalog_alias"] += 1
        self.component_alias_cache.add(cache_key)

    def ensure_media(
        self,
        source_code: str,
        original_url: str | None = None,
        local_path: str | None = None,
        asset_type: str = "image",
        width: int | None = None,
        height: int | None = None,
        metadata: dict | None = None,
    ) -> int:
        cache_key = (choose_text(original_url), choose_text(local_path))
        if cache_key in self.media_cache:
            return self.media_cache[cache_key]
        row = self.conn.execute(
            """
            SELECT media_id FROM media_asset
            WHERE COALESCE(original_url, '') = COALESCE(?, '')
              AND COALESCE(local_path, '') = COALESCE(?, '')
            """,
            (original_url, local_path),
        ).fetchone()
        if row:
            media_id = int(row[0])
            self.media_cache[cache_key] = media_id
            return media_id
        source_id = self.ensure_source(source_code)
        self.conn.execute(
            """
            INSERT INTO media_asset(source_id, asset_type, original_url, local_path, width, height, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                asset_type,
                choose_text(original_url),
                choose_text(local_path),
                width,
                height,
                safe_json_text(metadata or {}),
            ),
        )
        media_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.media_cache[cache_key] = media_id
        self.summary["media_asset"] += 1
        return media_id

    def ensure_bike_variant(
        self,
        source_code: str,
        source_entity_id: str,
        brand_name: str,
        bike_name: str,
        price_text: str | None = None,
        official_url: str | None = None,
        description: str | None = None,
        payload_json: str | None = None,
        model_year: int | None = None,
    ) -> int:
        source_key = (source_code, source_entity_id)
        if source_key in self.variant_source_cache:
            return self.variant_source_cache[source_key]
        brand_id = self.ensure_brand(brand_name)
        family_name = guess_family_name(brand_name, bike_name)
        model_name = guess_model_name(brand_name, bike_name)

        family_key = (brand_id or 0, family_name.lower())
        if family_key not in self.family_cache:
            row = self.conn.execute(
                "SELECT bike_family_id FROM bike_family WHERE brand_id IS ? AND family_name = ?",
                (brand_id, family_name),
            ).fetchone()
            if row:
                self.family_cache[family_key] = int(row[0])
            else:
                self.conn.execute(
                    """
                    INSERT INTO bike_family(brand_id, family_name)
                    VALUES (?, ?)
                    """,
                    (brand_id, family_name),
                )
                self.family_cache[family_key] = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                self.summary["bike_family"] += 1

        model_key = (self.family_cache[family_key], model_name.lower(), model_year)
        if model_key not in self.model_cache:
            row = self.conn.execute(
                """
                SELECT bike_model_id FROM bike_model
                WHERE bike_family_id = ? AND model_name = ? AND model_year IS ?
                """,
                (self.family_cache[family_key], model_name, model_year),
            ).fetchone()
            if row:
                self.model_cache[model_key] = int(row[0])
            else:
                self.conn.execute(
                    """
                    INSERT INTO bike_model(bike_family_id, model_name, model_year)
                    VALUES (?, ?, ?)
                    """,
                    (self.family_cache[family_key], model_name, model_year),
                )
                self.model_cache[model_key] = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                self.summary["bike_model"] += 1

        row = self.conn.execute(
            """
            SELECT bike_variant_id FROM bike_variant
            WHERE bike_model_id = ? AND variant_name = ?
            """,
            (self.model_cache[model_key], bike_name),
        ).fetchone()
        msrp_value, currency = parse_price_value(price_text)
        if row:
            bike_variant_id = int(row[0])
            self.conn.execute(
                """
                UPDATE bike_variant
                SET msrp_value = COALESCE(msrp_value, ?),
                    currency = COALESCE(currency, ?),
                    official_url = COALESCE(official_url, ?),
                    description = COALESCE(description, ?),
                    payload_json = COALESCE(payload_json, ?)
                WHERE bike_variant_id = ?
                """,
                (msrp_value, currency, official_url, description, payload_json, bike_variant_id),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO bike_variant(
                    bike_model_id, variant_name, msrp_value, currency, official_url, description, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.model_cache[model_key],
                    bike_name,
                    msrp_value,
                    currency,
                    official_url,
                    description,
                    payload_json,
                ),
            )
            bike_variant_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            self.summary["bike_variant"] += 1

        self.variant_source_cache[source_key] = bike_variant_id
        self.ensure_source_entity_map(source_code, "bike", source_entity_id, "bike_variant", bike_variant_id, 1.0)
        self.ensure_bike_variant_alias(
            bike_variant_id,
            bike_name,
            alias_type="name",
            source_code=source_code,
            source_entity_id=source_entity_id,
        )
        self.ensure_bike_variant_alias(bike_variant_id, model_name, alias_type="model_name")
        self.ensure_bike_variant_alias(bike_variant_id, family_name, alias_type="family_name")
        return bike_variant_id

    def ensure_component_catalog(
        self,
        canonical_key: str,
        component_name: str,
        brand_name: str | None = None,
        part_key: str | None = None,
        component_category: str | None = None,
        series_name: str | None = None,
        model_code: str | None = None,
        official_url: str | None = None,
        description: str | None = None,
        payload_json: str | None = None,
    ) -> int:
        canonical_key = normalize_slug(canonical_key).replace("-", "_")
        if canonical_key in self.component_cache:
            component_catalog_id = self.component_cache[canonical_key]
            self.ensure_component_catalog_alias(component_catalog_id, component_name, alias_type="name")
            self.ensure_component_catalog_alias(component_catalog_id, canonical_key, alias_type="canonical_key")
            self.ensure_component_catalog_alias(component_catalog_id, series_name, alias_type="series_name")
            self.ensure_component_catalog_alias(component_catalog_id, model_code, alias_type="model_code")
            return component_catalog_id
        row = self.conn.execute(
            "SELECT component_catalog_id FROM component_catalog WHERE canonical_key = ?",
            (canonical_key,),
        ).fetchone()
        if row:
            component_catalog_id = int(row[0])
            self.component_cache[canonical_key] = component_catalog_id
            self.ensure_component_catalog_alias(component_catalog_id, component_name, alias_type="name")
            self.ensure_component_catalog_alias(component_catalog_id, canonical_key, alias_type="canonical_key")
            self.ensure_component_catalog_alias(component_catalog_id, series_name, alias_type="series_name")
            self.ensure_component_catalog_alias(component_catalog_id, model_code, alias_type="model_code")
            return component_catalog_id
        brand_id = self.ensure_brand(brand_name)
        resolved_part_key = part_key or infer_part_key(component_name, component_category or "")
        part_taxonomy_id = self.ensure_part_taxonomy(
            resolved_part_key,
            resolved_part_key.replace("_", " ").title(),
            visualization_slot=resolved_part_key,
        )
        self.conn.execute(
            """
            INSERT INTO component_catalog(
                brand_id, part_taxonomy_id, component_name, canonical_key, component_category,
                series_name, model_code, official_url, description, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                brand_id,
                part_taxonomy_id,
                component_name,
                canonical_key,
                component_category,
                series_name,
                model_code,
                official_url,
                description,
                payload_json,
            ),
        )
        component_catalog_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.component_cache[canonical_key] = component_catalog_id
        self.summary["component_catalog"] += 1
        self.ensure_component_catalog_alias(component_catalog_id, component_name, alias_type="name")
        self.ensure_component_catalog_alias(component_catalog_id, canonical_key, alias_type="canonical_key")
        self.ensure_component_catalog_alias(component_catalog_id, series_name, alias_type="series_name")
        self.ensure_component_catalog_alias(component_catalog_id, model_code, alias_type="model_code")
        return component_catalog_id

    def ensure_source_entity_map(
        self,
        source_code: str,
        source_entity_type: str,
        source_entity_id: str,
        target_table: str,
        target_id: int,
        confidence: float = 1.0,
    ) -> None:
        source_id = self.ensure_source(source_code)
        self.conn.execute(
            """
            INSERT OR IGNORE INTO source_entity_map(
                source_id, source_entity_type, source_entity_id, target_table, target_id, match_confidence
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_id, source_entity_type, str(source_entity_id), target_table, target_id, confidence),
        )

    def ensure_image_item(
        self,
        file_key: str,
        source_code: str,
        local_path: str | None,
        original_url: str | None,
        dataset_version_id: int | None,
        split_name: str | None,
        image_role: str,
        is_side_view: bool,
        quality_score: float | None,
        width: int | None,
        height: int | None,
        source_record_key: str | None = None,
    ) -> int:
        if file_key in self.image_cache:
            return self.image_cache[file_key]
        media_id = self.ensure_media(
            source_code=source_code,
            original_url=original_url,
            local_path=local_path,
            width=width,
            height=height,
            metadata={"source_record_key": source_record_key} if source_record_key else {},
        )
        row = self.conn.execute(
            "SELECT image_id FROM image_item WHERE media_id = ?",
            (media_id,),
        ).fetchone()
        if row:
            image_id = int(row[0])
        else:
            self.conn.execute(
                """
                INSERT INTO image_item(
                    dataset_version_id, media_id, split_name, image_role, scene_type,
                    is_side_view, quality_score, source_record_key, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_version_id,
                    media_id,
                    split_name,
                    image_role,
                    "bicycle",
                    1 if is_side_view else 0,
                    quality_score,
                    source_record_key,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
            image_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            self.summary["image_item"] += 1
        self.image_cache[file_key] = image_id
        return image_id

    def ensure_bicycle_instance(self, image_id: int, view_label: str | None = None) -> int:
        if image_id in self.bike_instance_cache:
            return self.bike_instance_cache[image_id]
        row = self.conn.execute(
            "SELECT bicycle_instance_id FROM bicycle_instance WHERE image_id = ? AND instance_index = 1",
            (image_id,),
        ).fetchone()
        if row:
            bicycle_instance_id = int(row[0])
        else:
            self.conn.execute(
                """
                INSERT INTO bicycle_instance(image_id, instance_index, is_primary, view_label)
                VALUES (?, 1, 1, ?)
                """,
                (image_id, view_label),
            )
            bicycle_instance_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            self.summary["bicycle_instance"] += 1
        self.bike_instance_cache[image_id] = bicycle_instance_id
        return bicycle_instance_id

    def resolve_dataset_image_path(self, dataset_dir: Path, image_name: str) -> Path | None:
        candidates = [
            dataset_dir / image_name,
            dataset_dir / "assets" / image_name,
            dataset_dir / "repo" / image_name,
            dataset_dir / "repo" / "assets" / image_name,
            dataset_dir / "repo" / "Point_Detection_Hyperfeatures" / "assets" / image_name,
            dataset_dir / "repo" / "Text_Generation_with_GPT4o" / "assets" / image_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def ensure_dataset_sample_image(
        self,
        dataset_code: str,
        dataset_version_id: int,
        dataset_dir: Path,
        image_name: str,
        source_record_key: str,
        image_role: str = "dataset_image",
        split_name: str = "raw",
        is_side_view: bool = False,
    ) -> int | None:
        image_path = self.resolve_dataset_image_path(dataset_dir, image_name)
        if image_path is None:
            return None
        width = None
        height = None
        try:
            with Image.open(image_path) as image:
                width, height = image.size
        except Exception:
            pass
        image_id = self.ensure_image_item(
            file_key=str(image_path),
            source_code=dataset_code,
            local_path=str(image_path),
            original_url=None,
            dataset_version_id=dataset_version_id,
            split_name=split_name,
            image_role=image_role,
            is_side_view=is_side_view,
            quality_score=None,
            width=width,
            height=height,
            source_record_key=source_record_key,
        )
        self.ensure_bicycle_instance(image_id, view_label="side" if is_side_view else None)
        return image_id

    def ensure_annotation_task(
        self,
        task_name: str,
        dataset_version_id: int | None,
        tool_name: str,
        annotation_type: str,
        label_schema: list[str] | None = None,
        status: str = "active",
    ) -> int:
        if task_name in self.annotation_task_cache:
            return self.annotation_task_cache[task_name]
        row = self.conn.execute(
            "SELECT annotation_task_id FROM annotation_task WHERE task_name = ?",
            (task_name,),
        ).fetchone()
        if row:
            task_id = int(row[0])
        else:
            self.conn.execute(
                """
                INSERT INTO annotation_task(dataset_version_id, task_name, tool_name, annotation_type, label_schema_json, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_version_id,
                    task_name,
                    tool_name,
                    annotation_type,
                    safe_json_text(label_schema or []),
                    status,
                ),
            )
            task_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            self.summary["annotation_task"] += 1
        self.annotation_task_cache[task_name] = task_id
        return task_id

    def ensure_annotation_set(
        self,
        annotation_task_id: int,
        image_id: int,
        annotation_format: str,
        annotation_uri: str | None,
        quality_status: str | None,
        version_no: int = 1,
    ) -> int:
        row = self.conn.execute(
            """
            SELECT annotation_set_id FROM annotation_set
            WHERE annotation_task_id = ? AND image_id = ? AND version_no = ?
            """,
            (annotation_task_id, image_id, version_no),
        ).fetchone()
        if row:
            return int(row[0])
        self.conn.execute(
            """
            INSERT INTO annotation_set(
                annotation_task_id, image_id, annotation_format, annotation_uri, quality_status, version_no
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (annotation_task_id, image_id, annotation_format, annotation_uri, quality_status, version_no),
        )
        self.summary["annotation_set"] += 1
        return int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    def insert_offer_snapshot(
        self,
        source_code: str,
        offer_title: str,
        observed_at: str,
        component_catalog_id: int | None = None,
        bike_variant_id: int | None = None,
        price_value: float | None = None,
        currency: str | None = None,
        offer_url: str | None = None,
        offer_category: str | None = None,
        merchant_name: str | None = None,
        source_entity_id: str | None = None,
        payload: dict | None = None,
    ) -> None:
        source_id = self.ensure_source(source_code)
        merchant_id = self.ensure_merchant(merchant_name)
        self.conn.execute(
            """
            INSERT INTO offer_snapshot(
                source_id, merchant_id, component_catalog_id, bike_variant_id, source_entity_id,
                offer_title, offer_category, price_value, currency, offer_url, observed_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                merchant_id,
                component_catalog_id,
                bike_variant_id,
                source_entity_id,
                offer_title,
                offer_category,
                price_value,
                currency,
                offer_url,
                observed_at,
                safe_json_text(payload or {}),
            ),
        )
        self.summary["offer_snapshot"] += 1

    def insert_review_article(
        self,
        source_code: str,
        title: str,
        summary: str | None,
        review_url: str | None,
        rating_value: float | None = None,
        rating_scale: float | None = None,
        published_at: str | None = None,
        payload: dict | None = None,
    ) -> int:
        source_id = self.ensure_source(source_code)
        self.conn.execute(
            """
            INSERT INTO review_article(
                source_id, title, published_at, summary, rating_value, rating_scale, review_url, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                title,
                published_at,
                summary,
                rating_value,
                rating_scale,
                review_url,
                safe_json_text(payload or {}),
            ),
        )
        self.summary["review_article"] += 1
        return int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    def insert_review_target(
        self,
        review_article_id: int,
        brand_id: int | None = None,
        bike_variant_id: int | None = None,
        component_catalog_id: int | None = None,
        match_confidence: float = 1.0,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO review_target(
                review_article_id, brand_id, bike_variant_id, component_catalog_id, match_confidence
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (review_article_id, brand_id, bike_variant_id, component_catalog_id, match_confidence),
        )
        self.summary["review_target"] += 1

    def migrate_general_dataset_tables(self, general_db_path: Path) -> None:
        if not general_db_path.exists():
            return
        conn = sqlite3.connect(general_db_path)
        conn.row_factory = sqlite3.Row
        if table_exists(conn, "dataset_manifest"):
            rows = conn.execute("SELECT * FROM dataset_manifest").fetchall()
            for row in rows:
                dataset_name = choose_text(row["dataset_name"]) or "unknown_dataset"
                dataset_code = normalize_slug(dataset_name).replace("-", "_")
                source_id = self.ensure_source(dataset_code, dataset_name, "dataset")
                dataset_id = self.ensure_dataset(dataset_code, dataset_name, dataset_code)
                self.conn.execute(
                    """
                    UPDATE dataset
                    SET source_id = COALESCE(source_id, ?),
                        homepage_url = COALESCE(homepage_url, ?),
                        local_path = COALESCE(local_path, ?),
                        manifest_json = COALESCE(manifest_json, ?)
                    WHERE dataset_id = ?
                    """,
                    (
                        source_id,
                        row["source_url"],
                        row["local_path"],
                        safe_json_text(
                            {
                                "status": row["status"],
                                "detail": row["detail"],
                                "created_at": row["created_at"],
                            }
                        ),
                        dataset_id,
                    ),
                )
                self.ensure_dataset_version(dataset_code, "latest", row["status"])
        if table_exists(conn, "source_runs"):
            rows = conn.execute("SELECT * FROM source_runs").fetchall()
            for row in rows:
                run_at = choose_text(row["run_at"]) or datetime.utcnow().isoformat(timespec="seconds")
                self.ensure_ingestion_run(
                    source_code=row["source_name"],
                    pipeline_stage="legacy_import",
                    started_at=run_at,
                    status="done",
                    raw_path=row["raw_file"],
                    record_count=int(row["record_count"] or 0),
                )
        conn.close()

    def migrate_open_dataset_artifacts(self) -> None:
        raw_datasets_dir = self.project_root / "data" / "raw" / "datasets"
        if not raw_datasets_dir.exists():
            return

        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        structured_extensions = {".json", ".csv", ".tsv", ".txt", ".md", ".yaml", ".yml", ".html"}

        for dataset_dir in sorted(path for path in raw_datasets_dir.iterdir() if path.is_dir()):
            dataset_code = normalize_slug(dataset_dir.name).replace("-", "_")
            manifest_path = dataset_dir / "manifest.json"
            manifest_payload: dict = {}
            if manifest_path.exists():
                with manifest_path.open("r", encoding="utf-8") as fh:
                    manifest_payload = json.load(fh)

            dataset_name = (
                choose_text(manifest_payload.get("dataset_name"))
                or KNOWN_DATASETS.get(dataset_code)
                or dataset_dir.name
            )
            source_url = choose_text(
                manifest_payload.get("source_url"),
                manifest_payload.get("repo"),
            )
            source_id = self.ensure_source(dataset_code, dataset_name, "dataset")
            dataset_id = self.ensure_dataset(dataset_code, dataset_name, dataset_code)
            dataset_version_id = self.ensure_dataset_version(
                dataset_code,
                "latest",
                choose_text(manifest_payload.get("status"), "scanned_from_raw_datasets"),
            )
            self.conn.execute(
                """
                UPDATE dataset
                SET source_id = COALESCE(source_id, ?),
                    homepage_url = COALESCE(homepage_url, ?),
                    local_path = COALESCE(local_path, ?),
                    manifest_json = ?
                WHERE dataset_id = ?
                """,
                (
                    source_id,
                    source_url,
                    str(dataset_dir),
                    safe_json_text(manifest_payload),
                    dataset_id,
                ),
            )

            started_at = choose_text(manifest_payload.get("downloaded_at")) or datetime.utcnow().isoformat(timespec="seconds")
            scanned_files = [
                path
                for path in dataset_dir.rglob("*")
                if path.is_file() and ".cache" not in path.parts and "__pycache__" not in path.parts
            ]
            self.ensure_ingestion_run(
                source_code=dataset_code,
                pipeline_stage="dataset_scan",
                started_at=started_at,
                status=choose_text(manifest_payload.get("status"), "done") or "done",
                raw_path=str(dataset_dir),
                record_count=len(scanned_files),
                note="扫描 raw/datasets 中的开源数据集文件",
            )
            run_id = int(
                self.conn.execute(
                    """
                    SELECT run_id FROM ingestion_run
                    WHERE source_id = ? AND pipeline_stage = 'dataset_scan'
                    ORDER BY run_id DESC LIMIT 1
                    """,
                    (source_id,),
                ).fetchone()[0]
            )

            for file_path in scanned_files:
                rel_path = file_path.relative_to(dataset_dir).as_posix()
                suffix = file_path.suffix.lower()
                file_record_payload = {
                    "relative_path": rel_path,
                    "size_bytes": file_path.stat().st_size,
                }

                if suffix in structured_extensions:
                    preview = None
                    try:
                        preview = file_path.read_text(encoding="utf-8", errors="ignore")[:2000]
                    except OSError:
                        preview = None
                    file_record_payload["text_preview"] = preview

                source_record_id = self.ensure_source_record(
                    run_id=run_id,
                    source_entity_type="dataset_file",
                    source_entity_id=rel_path,
                    raw_payload=file_record_payload,
                )

                if suffix not in image_extensions:
                    continue

                width = None
                height = None
                try:
                    with Image.open(file_path) as image:
                        width, height = image.size
                except Exception:
                    pass

                sha256 = file_sha256(file_path)
                media_id = self.ensure_media(
                source_code=dataset_code,
                    original_url=None,
                    local_path=str(file_path),
                    asset_type="image",
                    width=width,
                    height=height,
                    metadata={
                        "dataset_code": dataset_code,
                        "relative_path": rel_path,
                        "sha256": sha256,
                    },
                )
                if sha256:
                    self.conn.execute(
                        "UPDATE media_asset SET sha256 = COALESCE(sha256, ?) WHERE media_id = ?",
                        (sha256, media_id),
                    )

                image_role = "dataset_image"
                lower_rel = rel_path.lower()
                if "asset" in lower_rel or lower_rel.startswith("repo/"):
                    image_role = "dataset_asset"
                image_id = self.ensure_image_item(
                    file_key=str(file_path),
                    source_code=dataset_code,
                    local_path=str(file_path),
                    original_url=None,
                    dataset_version_id=dataset_version_id,
                    split_name="raw",
                    image_role=image_role,
                    is_side_view=False,
                    quality_score=None,
                    width=width,
                    height=height,
                    source_record_key=rel_path,
                )
                self.ensure_bicycle_instance(image_id, view_label=None)

            if dataset_code == "geobiked":
                self.migrate_geobiked_structured_records(
                    dataset_dir=dataset_dir,
                    dataset_version_id=dataset_version_id,
                    run_id=run_id,
                )

    def migrate_geobiked_structured_records(
        self,
        dataset_dir: Path,
        dataset_version_id: int,
        run_id: int,
    ) -> None:
        annotations_path = dataset_dir / "repo" / "Point_Detection_Hyperfeatures" / "annotations" / "geopoints_full_swapped_2.json"
        if annotations_path.exists():
            payload = json.loads(annotations_path.read_text(encoding="utf-8"))
            rel_path = annotations_path.relative_to(dataset_dir).as_posix()
            source_record_id = self.ensure_source_record(
                run_id=run_id,
                source_entity_type="dataset_file",
                source_entity_id=rel_path,
                raw_payload={
                    "relative_path": rel_path,
                    "record_count": len(payload),
                    "structured_type": "geobiked_keypoints",
                },
            )
            for row in payload:
                image_name = choose_text(row.get("image_path")) or "unknown"
                sample_key = Path(image_name).stem
                self.ensure_dataset_sample_image(
                    dataset_code="geobiked",
                    dataset_version_id=dataset_version_id,
                    dataset_dir=dataset_dir,
                    image_name=image_name,
                    source_record_key=f"geobiked:{image_name}",
                    image_role="dataset_image",
                    split_name="raw",
                    is_side_view=True,
                )
                points = row.get("image_points") or []
                bbox_value = row.get("bounding_box")
                bbox_json = None
                if bbox_value not in (None, "", "unspecified"):
                    bbox_json = safe_json_text(bbox_value)
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO dataset_annotation_record(
                        dataset_version_id, source_record_id, sample_key, image_rel_path,
                        annotation_type, category, source_pose, target_pose, mirror_flag,
                        viewpoint_variation, bounding_box_json, points_json, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dataset_version_id,
                        source_record_id,
                        sample_key,
                        image_name,
                        "geometric_keypoints",
                        choose_text(row.get("category")),
                        choose_text(row.get("source_pose")),
                        choose_text(row.get("target_pose")),
                        choose_text(row.get("mirror")),
                        choose_number(row.get("viewpoint_variation")),
                        bbox_json,
                        safe_json_text(points),
                        safe_json_text(row),
                    ),
                )
                self.summary["dataset_annotation_record"] += 1

                for feature_name in ("category", "source_pose", "target_pose", "mirror", "viewpoint_variation"):
                    feature_value = row.get(feature_name)
                    self.conn.execute(
                        """
                        INSERT OR IGNORE INTO dataset_feature_record(
                            dataset_version_id, source_record_id, sample_key, image_rel_path, feature_group,
                            feature_name, feature_value_text, feature_value_num, unit_text, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            dataset_version_id,
                            source_record_id,
                            sample_key,
                            image_name,
                            "geobiked_keypoints_meta",
                            feature_name,
                            None if isinstance(feature_value, (int, float)) else choose_text(feature_value),
                            choose_number(feature_value),
                            None,
                            safe_json_text({"source_file": rel_path}),
                        ),
                    )
                    self.summary["dataset_feature_record"] += 1

        for descriptions_path in sorted((dataset_dir / "repo" / "Text_Generation_with_GPT4o").glob("*.csv")):
            rows = load_csv_rows(descriptions_path)
            rel_path = descriptions_path.relative_to(dataset_dir).as_posix()
            source_record_id = self.ensure_source_record(
                run_id=run_id,
                source_entity_type="dataset_file",
                source_entity_id=rel_path,
                raw_payload={
                    "relative_path": rel_path,
                    "record_count": len(rows),
                    "structured_type": "geobiked_descriptions",
                },
            )
            description_source = descriptions_path.stem
            for row in rows:
                image_name = choose_text(row.get("image"))
                sample_key = Path(image_name).stem if image_name else choose_text(row.get("id"))
                if image_name:
                    self.ensure_dataset_sample_image(
                        dataset_code="geobiked",
                        dataset_version_id=dataset_version_id,
                        dataset_dir=dataset_dir,
                        image_name=image_name,
                        source_record_key=f"geobiked:{image_name}",
                        image_role="dataset_image",
                        split_name="raw",
                        is_side_view=True,
                    )
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO dataset_text_description(
                        dataset_version_id, source_record_id, sample_key, image_rel_path, description_source,
                        length_label, vibe_label, style_label, description_text, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dataset_version_id,
                        source_record_id,
                        sample_key,
                        image_name,
                        description_source,
                        choose_text(row.get("length")),
                        choose_text(row.get("vibe")),
                        choose_text(row.get("style")),
                        choose_text(row.get("description")) or "",
                        safe_json_text(row),
                    ),
                )
                self.summary["dataset_text_description"] += 1

        parameter_candidates = list(dataset_dir.rglob("GeoBiked_parameters.csv"))
        for parameters_path in parameter_candidates:
            rows = load_csv_rows(parameters_path)
            rel_path = parameters_path.relative_to(dataset_dir).as_posix()
            source_record_id = self.ensure_source_record(
                run_id=run_id,
                source_entity_type="dataset_file",
                source_entity_id=rel_path,
                raw_payload={
                    "relative_path": rel_path,
                    "record_count": len(rows),
                    "structured_type": "geobiked_parameters",
                },
            )
            for row in rows:
                sample_key = choose_text(row.get("Bike index"), row.get("bike_index"), row.get("id"))
                if not sample_key:
                    continue
                image_name = choose_text(row.get("image"), row.get("image_path"))
                for feature_name, feature_value in row.items():
                    if feature_name in {"Bike index", "bike_index", "id", "image", "image_path"}:
                        continue
                    text_value = choose_text(feature_value)
                    if text_value is None:
                        continue
                    self.conn.execute(
                        """
                        INSERT OR IGNORE INTO dataset_feature_record(
                            dataset_version_id, source_record_id, sample_key, image_rel_path, feature_group,
                            feature_name, feature_value_text, feature_value_num, unit_text, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            dataset_version_id,
                            source_record_id,
                            sample_key,
                            image_name,
                            "geobiked_parameters",
                            feature_name,
                            text_value if choose_number(text_value) is None else None,
                            choose_number(text_value),
                            "mm" if feature_name.lower().startswith(("x_", "y_")) else None,
                            safe_json_text({"source_file": rel_path}),
                        ),
                    )
                    self.summary["dataset_feature_record"] += 1

    def migrate_official_products(self, official_db_path: Path) -> None:
        if not official_db_path.exists():
            return
        conn = sqlite3.connect(official_db_path)
        conn.row_factory = sqlite3.Row
        bike_specs_by_key: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
        bike_components_by_key: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
        component_specs_by_key: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)

        for row in conn.execute("SELECT * FROM official_bike_specs").fetchall():
            bike_specs_by_key[(row["bike_source"], row["bike_source_id"])].append(row)
        for row in conn.execute("SELECT * FROM official_bike_components").fetchall():
            bike_components_by_key[(row["bike_source"], row["bike_source_id"])].append(row)
        for row in conn.execute("SELECT * FROM official_component_specs").fetchall():
            component_specs_by_key[(row["component_source"], row["component_source_id"])].append(row)

        for row in conn.execute("SELECT * FROM official_bikes ORDER BY brand, bike_name").fetchall():
            bike_variant_id = self.ensure_bike_variant(
                source_code=row["source"],
                source_entity_id=row["source_id"],
                brand_name=row["brand"],
                bike_name=row["bike_name"],
                price_text=row["price_text"],
                official_url=row["bike_url"],
                description=row["description"],
                payload_json=row["payload_json"],
            )
            for spec in bike_specs_by_key[(row["source"], row["source_id"])]:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO bike_variant_spec(
                        bike_variant_id, spec_group, spec_name, spec_value, source_priority
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        bike_variant_id,
                        "official_spec",
                        spec["spec_name"],
                        spec["spec_value"],
                        1,
                    ),
                )
                self.summary["bike_variant_spec"] += 1

            for view_type, url_field in (
                ("front", "front_view_url"),
                ("side", "side_view_url"),
                ("rear", "rear_view_url"),
            ):
                url = choose_text(row[url_field])
                if not url:
                    continue
                media_id = self.ensure_media(row["source"], original_url=url, asset_type="image")
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO bike_media(bike_variant_id, media_id, view_type, sort_order)
                    VALUES (?, ?, ?, 1)
                    """,
                    (bike_variant_id, media_id, view_type),
                )
                self.summary["bike_media"] += 1

            if row["price_text"]:
                msrp_value, currency = parse_price_value(row["price_text"])
                self.insert_offer_snapshot(
                    source_code=row["source"],
                    source_entity_id=row["source_id"],
                    offer_title=row["bike_name"],
                    observed_at=date.today().isoformat(),
                    bike_variant_id=bike_variant_id,
                    price_value=msrp_value,
                    currency=currency,
                    offer_url=row["bike_url"],
                    offer_category="official_msrp",
                    merchant_name=row["brand"],
                )

            for component in bike_components_by_key[(row["source"], row["source_id"])]:
                part_key = infer_part_key(component["component_name"], component["component_value"])
                component_name = choose_text(component["component_value"], component["component_name"]) or "Unknown Component"
                canonical_key = choose_text(component["normalized_component_key"]) or normalize_component_key(
                    component["component_name"] or "",
                    component["component_value"] or "",
                )
                component_brand = choose_text(component["inferred_brand"], infer_brand(component_name), row["brand"])
                component_catalog_id = self.ensure_component_catalog(
                    canonical_key=canonical_key,
                    component_name=component_name,
                    brand_name=component_brand,
                    part_key=part_key,
                    component_category=component["component_name"],
                    description=f'{component["component_name"]}: {component["component_value"]}',
                    payload_json=safe_json_text(
                        {
                            "spec_name": component["component_name"],
                            "spec_value": component["component_value"],
                        }
                    ),
                )
                self.component_key_map[canonical_key] = component_catalog_id
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO bike_build_component(
                        bike_variant_id, part_taxonomy_id, component_catalog_id, slot_name,
                        spec_name, spec_value, inferred_brand_text, source_priority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bike_variant_id,
                        self.ensure_part_taxonomy(part_key, part_key.replace("_", " ").title(), visualization_slot=part_key),
                        component_catalog_id,
                        part_key,
                        component["component_name"],
                        component["component_value"],
                        component["inferred_brand"],
                        1,
                    ),
                )
                self.summary["bike_build_component"] += 1

        for row in conn.execute("SELECT * FROM official_components ORDER BY brand, component_name").fetchall():
            part_key = infer_part_key(row["component_name"], row["component_category"] or "")
            canonical_key = normalize_component_key(row["component_name"] or "", row["component_category"] or "")
            component_catalog_id = self.ensure_component_catalog(
                canonical_key=canonical_key,
                component_name=row["component_name"],
                brand_name=row["brand"],
                part_key=part_key,
                component_category=row["component_category"],
                official_url=row["component_url"],
                description=row["description"],
                payload_json=row["payload_json"],
                model_code=row["source_id"],
            )
            self.component_key_map[canonical_key] = component_catalog_id
            self.ensure_source_entity_map(row["source"], "component", row["source_id"], "component_catalog", component_catalog_id, 1.0)
            if row["image_url"]:
                media_id = self.ensure_media(row["source"], original_url=row["image_url"], asset_type="image")
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO component_media(component_catalog_id, media_id, view_type, sort_order)
                    VALUES (?, ?, 'detail', 1)
                    """,
                    (component_catalog_id, media_id),
                )
                self.summary["component_media"] += 1
            for spec in component_specs_by_key[(row["source"], row["source_id"])]:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO component_catalog_spec(
                        component_catalog_id, spec_group, spec_name, spec_value, source_priority
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        component_catalog_id,
                        "official_spec",
                        spec["spec_name"],
                        spec["spec_value"],
                        1,
                    ),
                )
                self.summary["component_catalog_spec"] += 1
            if row["price_text"]:
                price_value, currency = parse_price_value(row["price_text"])
                self.insert_offer_snapshot(
                    source_code=row["source"],
                    source_entity_id=row["source_id"],
                    offer_title=row["component_name"],
                    observed_at=date.today().isoformat(),
                    component_catalog_id=component_catalog_id,
                    price_value=price_value,
                    currency=currency,
                    offer_url=row["component_url"],
                    offer_category="official_msrp",
                    merchant_name=row["brand"],
                )
        conn.close()

    def migrate_market_and_reviews(self, general_db_path: Path, official_db_path: Path) -> None:
        if general_db_path.exists():
            conn = sqlite3.connect(general_db_path)
            conn.row_factory = sqlite3.Row
            if table_exists(conn, "components"):
                for row in conn.execute("SELECT * FROM components").fetchall():
                    component_name = choose_text(row["name"]) or "Unknown Component"
                    part_key = infer_part_key(component_name, row["category"] or "")
                    canonical_key = normalize_component_key(component_name, row["category"] or "")
                    component_catalog_id = self.ensure_component_catalog(
                        canonical_key=canonical_key,
                        component_name=component_name,
                        brand_name=row["manufacturer"],
                        part_key=part_key,
                        component_category=row["category"],
                        official_url=row["url"],
                        payload_json=row["payload_json"],
                    )
                    self.component_key_map.setdefault(canonical_key, component_catalog_id)
                    if row["price_text"] or row["price_value"] is not None:
                        self.insert_offer_snapshot(
                            source_code=row["source"],
                            source_entity_id=row["source_id"],
                            offer_title=component_name,
                            observed_at=date.today().isoformat(),
                            component_catalog_id=component_catalog_id,
                            price_value=choose_number(row["price_value"], parse_price_value(row["price_text"])[0]),
                            currency=choose_text(row["currency"], parse_price_value(row["price_text"])[1]),
                            offer_url=row["url"],
                            offer_category=row["category"],
                            merchant_name=choose_text(row["manufacturer"], row["source"]),
                            payload={"rating_text": row["rating_text"]},
                        )
                    if row["rating_value"] is not None:
                        review_article_id = self.insert_review_article(
                            source_code=row["source"],
                            title=f"{component_name} user rating",
                            summary=None,
                            review_url=row["url"],
                            rating_value=choose_number(row["rating_value"]),
                            rating_scale=5.0,
                            payload={
                                "rating_text": row["rating_text"],
                                "review_count": row["review_count"],
                                "origin": "merchant_listing_rating",
                            },
                        )
                        self.insert_review_target(
                            review_article_id,
                            component_catalog_id=component_catalog_id,
                            match_confidence=0.95,
                        )
            if table_exists(conn, "reviews"):
                for row in conn.execute("SELECT * FROM reviews").fetchall():
                    payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
                    rating_value = choose_number(payload.get("rating_value"))
                    if rating_value is None:
                        rating_value, _ = parse_rating_value(
                            payload.get("rating_text")
                            if row["payload_json"] else None
                        )
                    brand_hint = choose_text(payload.get("reviewed_brand"), payload.get("brand_hint"), row["brand_hint"])
                    reviewed_name = choose_text(payload.get("reviewed_name"))
                    reviewed_category = choose_text(payload.get("reviewed_category"), row["category"], row["subtype"])
                    component_catalog_id = None
                    if reviewed_name or (row["category"] and row["source_id"] and "/components/" in row["source_id"]):
                        component_display_name = choose_text(reviewed_name, row["title"]) or "Unknown Reviewed Component"
                        part_key = infer_part_key(component_display_name, reviewed_category or "")
                        canonical_key = normalize_component_key(component_display_name, reviewed_category or "")
                        component_catalog_id = self.ensure_component_catalog(
                            canonical_key=canonical_key,
                            component_name=component_display_name,
                            brand_name=brand_hint,
                            part_key=part_key,
                            component_category=reviewed_category,
                            official_url=row["url"],
                            description=choose_text(row["summary"]),
                            payload_json=row["payload_json"],
                        )
                    review_article_id = self.insert_review_article(
                        source_code=row["source"],
                        title=row["title"],
                        summary=row["summary"],
                        review_url=row["url"],
                        rating_value=rating_value,
                        rating_scale=5.0 if rating_value is not None else None,
                        payload={
                            "category": row["category"],
                            "subtype": row["subtype"],
                            "reviewed_name": reviewed_name,
                            "reviewed_brand": brand_hint,
                            "reviewed_category": reviewed_category,
                        },
                    )
                    if component_catalog_id is not None:
                        self.insert_review_target(
                            review_article_id,
                            component_catalog_id=component_catalog_id,
                            match_confidence=0.9,
                        )
                    brand_id = self.ensure_brand(brand_hint)
                    if brand_id is not None and component_catalog_id is None:
                        self.insert_review_target(review_article_id, brand_id=brand_id, match_confidence=0.6)
            conn.close()

        if not official_db_path.exists():
            return
        conn = sqlite3.connect(official_db_path)
        conn.row_factory = sqlite3.Row
        if table_exists(conn, "component_market_offers"):
            for row in conn.execute("SELECT * FROM component_market_offers").fetchall():
                component_catalog_id = self.component_key_map.get(row["component_key"])
                if component_catalog_id is None:
                    part_key = infer_part_key(row["matched_component_name"], row["category"] or "")
                    component_catalog_id = self.ensure_component_catalog(
                        canonical_key=row["component_key"],
                        component_name=choose_text(row["matched_component_name"], row["offer_title"]) or "Unknown Component",
                        brand_name=row["manufacturer"],
                        part_key=part_key,
                        component_category=row["category"],
                        official_url=row["url"],
                        payload_json=row["payload_json"],
                    )
                    self.component_key_map[row["component_key"]] = component_catalog_id
                self.insert_offer_snapshot(
                    source_code=row["offer_source"],
                    source_entity_id=row["offer_source_id"],
                    offer_title=row["offer_title"],
                    observed_at=date.today().isoformat(),
                    component_catalog_id=component_catalog_id,
                    price_value=row["price_value"],
                    currency=row["currency"],
                    offer_url=row["url"],
                    offer_category=row["category"],
                    merchant_name=choose_text(row["manufacturer"], row["offer_source"]),
                    payload={"matched_component_name": row["matched_component_name"]},
                )
        if table_exists(conn, "component_quality_reviews"):
            for row in conn.execute("SELECT * FROM component_quality_reviews").fetchall():
                component_catalog_id = self.component_key_map.get(row["component_key"])
                if component_catalog_id is None:
                    part_key = infer_part_key(row["review_title"], row["category"] or "")
                    component_catalog_id = self.ensure_component_catalog(
                        canonical_key=row["component_key"],
                        component_name=row["review_title"],
                        brand_name=row["brand_hint"],
                        part_key=part_key,
                        component_category=row["category"],
                    )
                    self.component_key_map[row["component_key"]] = component_catalog_id
                review_article_id = self.insert_review_article(
                    source_code=row["review_source"],
                    title=row["review_title"],
                    summary=row["summary"],
                    review_url=row["url"],
                    rating_value=row["rating_value"],
                    rating_scale=5.0 if row["rating_value"] is not None else None,
                    payload={"category": row["category"], "subtype": row["subtype"]},
                )
                self.insert_review_target(
                    review_article_id,
                    component_catalog_id=component_catalog_id,
                    match_confidence=1.0,
                )
        conn.close()

    def migrate_annotations(self) -> None:
        manifest_root = self.project_root / "data" / "annotations" / "manifests"
        cvat_root = self.project_root / "data" / "annotations" / "cvat_import" / "side_view_dataset"
        export_root = self.project_root / "data" / "annotations" / "exports"

        raw_dataset_version_id = self.ensure_dataset_version(
            "side_view_annotation_candidates",
            "v1",
            "来自 bike_image_prefiltered/annotation_manifest 的候选图",
        )
        cvat_dataset_version_id = self.ensure_dataset_version(
            "cvat_side_view_dataset",
            "v1",
            "来自 CVAT 导入目录的侧视图数据",
        )

        label_schema_path = cvat_root / "labels.txt"
        label_schema = [
            line.strip()
            for line in label_schema_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ] if label_schema_path.exists() else ["frame", "front_wheel", "rear_wheel", "fork", "handlebar", "saddle", "drivetrain", "brake"]
        for label in label_schema:
            self.ensure_part_taxonomy(infer_part_key(label), label.replace("_", " ").title(), visualization_slot=infer_part_key(label))

        prefilter_rows = load_csv_rows(manifest_root / "bike_image_prefiltered.csv")
        annotation_rows = load_csv_rows(manifest_root / "annotation_manifest.csv")
        cvat_rows = load_csv_rows(cvat_root / "cvat_manifest.csv")

        raw_task_id = self.ensure_annotation_task(
            task_name="side_view_candidate_queue",
            dataset_version_id=raw_dataset_version_id,
            tool_name="manifest",
            annotation_type="candidate_selection",
            label_schema=label_schema,
        )
        cvat_task_id = self.ensure_annotation_task(
            task_name="cvat_side_view_polygon",
            dataset_version_id=cvat_dataset_version_id,
            tool_name="CVAT",
            annotation_type="instance_segmentation",
            label_schema=label_schema,
        )

        rows_by_file: dict[str, dict] = {}
        for row in annotation_rows + prefilter_rows:
            file_key = Path(choose_text(row.get("absolute_image_path"), row.get("image_path"), row.get("file_name")) or "unknown").name
            rows_by_file[file_key] = row

        for row in prefilter_rows:
            local_path = choose_text(row.get("absolute_image_path"), row.get("image_path"))
            file_key = Path(local_path).name if local_path else f'{row.get("source", "unknown")}_{row.get("source_id", "unknown")}'
            image_id = self.ensure_image_item(
                file_key=file_key,
                source_code=choose_text(row.get("source"), "annotation_prefilter") or "annotation_prefilter",
                local_path=local_path,
                original_url=choose_text(row.get("image_url")),
                dataset_version_id=raw_dataset_version_id,
                split_name="candidate",
                image_role="side_view_candidate",
                is_side_view=row.get("prefilter_decision") in {"keep", "review"},
                quality_score=choose_number(row.get("prefilter_score")),
                width=int(float(row["width"])) if row.get("width") else None,
                height=int(float(row["height"])) if row.get("height") else None,
                source_record_key=choose_text(row.get("source_id")),
            )
            self.ensure_bicycle_instance(image_id, view_label="side" if row.get("prefilter_decision") in {"keep", "review"} else None)
            self.ensure_annotation_set(
                annotation_task_id=raw_task_id,
                image_id=image_id,
                annotation_format="csv_manifest",
                annotation_uri=str(manifest_root / "bike_image_prefiltered.csv"),
                quality_status=row.get("prefilter_decision"),
            )

        for row in cvat_rows:
            local_path = choose_text(row.get("exported_image_path"), row.get("absolute_image_path"))
            file_key = Path(choose_text(row.get("exported_file_name"), local_path) or "unknown").name
            image_id = self.ensure_image_item(
                file_key=file_key,
                source_code=choose_text(row.get("source"), "cvat_side_view_dataset") or "cvat_side_view_dataset",
                local_path=local_path,
                original_url=choose_text(row.get("image_url")),
                dataset_version_id=cvat_dataset_version_id,
                split_name="train",
                image_role="side_view_cvat",
                is_side_view=True,
                quality_score=choose_number(row.get("prefilter_score")),
                width=int(float(row["width"])) if row.get("width") else None,
                height=int(float(row["height"])) if row.get("height") else None,
                source_record_key=choose_text(row.get("source_id")),
            )
            bicycle_instance_id = self.ensure_bicycle_instance(image_id, view_label="side")
            annotation_set_id = self.ensure_annotation_set(
                annotation_task_id=cvat_task_id,
                image_id=image_id,
                annotation_format="cvat_manifest",
                annotation_uri=str(cvat_root / "cvat_manifest.csv"),
                quality_status=row.get("cvat_status"),
            )
            title = choose_text(row.get("title"))
            manufacturer = choose_text(row.get("manufacturer_name"))
            if manufacturer and title:
                brand_id = self.ensure_brand(manufacturer)
                if brand_id is not None:
                    self.conn.execute(
                        """
                        INSERT OR IGNORE INTO annotated_object(
                            annotation_set_id, bicycle_instance_id, part_taxonomy_id, object_class, geometry_type, visibility, attributes_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            annotation_set_id,
                            bicycle_instance_id,
                            self.ensure_part_taxonomy("bicycle", "Bicycle", visualization_slot="bicycle"),
                            "bicycle",
                            "bbox",
                            "visible",
                            safe_json_text({"title": title, "manufacturer_name": manufacturer}),
                        ),
                    )
                    self.summary["annotated_object"] += 1

        silhouette_root = export_root / "white_silhouettes"
        silhouette_manifest_path = silhouette_root / "silhouette_manifest.json"
        if silhouette_manifest_path.exists():
            silhouette_dataset_version_id = self.ensure_dataset_version(
                "white_background_silhouettes",
                "v1",
                "来自白底整车图自动生成的剪影、透明剪影与二值掩膜",
            )
            silhouette_rows = json.loads(silhouette_manifest_path.read_text(encoding="utf-8"))
            for row in silhouette_rows:
                width = None
                height = None
                size = row.get("size") or []
                if len(size) >= 2:
                    width = int(size[0])
                    height = int(size[1])
                input_path = choose_text(row.get("input_path"))
                stem = Path(choose_text(input_path) or "unknown").stem
                derived_assets = [
                    ("white_background_mask", choose_text(row.get("mask_path"))),
                    ("white_background_silhouette", choose_text(row.get("silhouette_path"))),
                    ("white_background_silhouette_rgba", choose_text(row.get("silhouette_rgba_path"))),
                ]
                for image_role, local_path in derived_assets:
                    if not local_path or not Path(local_path).exists():
                        continue
                    file_key = f"{stem}:{image_role}"
                    image_id = self.ensure_image_item(
                        file_key=file_key,
                        source_code="white_background_silhouettes",
                        local_path=local_path,
                        original_url=None,
                        dataset_version_id=silhouette_dataset_version_id,
                        split_name="derived",
                        image_role=image_role,
                        is_side_view=True,
                        quality_score=None,
                        width=width,
                        height=height,
                        source_record_key=input_path,
                    )
                    self.ensure_bicycle_instance(
                        image_id,
                        view_label="side" if image_role != "white_background_mask" else None,
                    )

        coco_path = export_root / "instances_default.json"
        if not coco_path.exists():
            return
        payload = json.loads(coco_path.read_text(encoding="utf-8"))
        coco_task_id = self.ensure_annotation_task(
            task_name="coco_instance_segmentation_export",
            dataset_version_id=cvat_dataset_version_id,
            tool_name="COCO",
            annotation_type="instance_segmentation",
            label_schema=label_schema,
            status="done",
        )
        categories = {int(cat["id"]): cat["name"] for cat in payload.get("categories", [])}
        images_by_id = {int(item["id"]): item for item in payload.get("images", [])}
        annotations_by_image: dict[int, list[dict]] = defaultdict(list)
        for ann in payload.get("annotations", []):
            annotations_by_image[int(ann["image_id"])].append(ann)

        for image_payload in payload.get("images", []):
            image_id_value = int(image_payload["id"])
            file_name = Path(image_payload["file_name"]).name
            image_id = self.image_cache.get(file_name)
            if image_id is None:
                local_path = str(cvat_root / "images" / file_name)
                image_id = self.ensure_image_item(
                    file_key=file_name,
                    source_code="cvat_side_view_dataset",
                    local_path=local_path if Path(local_path).exists() else None,
                    original_url=None,
                    dataset_version_id=cvat_dataset_version_id,
                    split_name="train",
                    image_role="side_view_cvat",
                    is_side_view=True,
                    quality_score=None,
                    width=int(image_payload.get("width") or 0) or None,
                    height=int(image_payload.get("height") or 0) or None,
                )
            bicycle_instance_id = self.ensure_bicycle_instance(image_id, view_label="side")
            annotation_set_id = self.ensure_annotation_set(
                annotation_task_id=coco_task_id,
                image_id=image_id,
                annotation_format="coco",
                annotation_uri=str(coco_path),
                quality_status="done",
            )
            for ann in annotations_by_image.get(image_id_value, []):
                category_name = categories.get(int(ann["category_id"]), "component")
                part_key = infer_part_key(category_name)
                part_taxonomy_id = self.ensure_part_taxonomy(
                    part_key,
                    category_name.replace("_", " ").title(),
                    visualization_slot=part_key,
                )
                segmentation = ann.get("segmentation") or []
                geometry_type = "polygon" if isinstance(segmentation, list) and segmentation else "bbox"
                self.conn.execute(
                    """
                    INSERT INTO annotated_object(
                        annotation_set_id, bicycle_instance_id, part_taxonomy_id, object_class, geometry_type,
                        area_value, is_crowd, visibility, bbox_x, bbox_y, bbox_width, bbox_height, attributes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        annotation_set_id,
                        bicycle_instance_id,
                        part_taxonomy_id,
                        "part",
                        geometry_type,
                        ann.get("area"),
                        int(ann.get("iscrowd", 0)),
                        "visible",
                        ann.get("bbox", [None, None, None, None])[0] if ann.get("bbox") else None,
                        ann.get("bbox", [None, None, None, None])[1] if ann.get("bbox") else None,
                        ann.get("bbox", [None, None, None, None])[2] if ann.get("bbox") else None,
                        ann.get("bbox", [None, None, None, None])[3] if ann.get("bbox") else None,
                        safe_json_text({"category_name": category_name}),
                    ),
                )
                annotated_object_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                self.summary["annotated_object"] += 1
                self.conn.execute(
                    """
                    INSERT INTO object_geometry(
                        annotated_object_id, geometry_kind, geometry_json, mask_rle, keypoints_json, polygon_count
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        annotated_object_id,
                        geometry_type,
                        safe_json_text(segmentation if segmentation else ann.get("bbox")),
                        None if isinstance(segmentation, list) else choose_text(segmentation),
                        None,
                        len(segmentation) if isinstance(segmentation, list) else 0,
                    ),
                )
                self.summary["object_geometry"] += 1

    def rebuild_metrics(self) -> None:
        snapshot_date = date.today().isoformat()
        self.conn.execute("DELETE FROM component_metric_snapshot")
        self.conn.execute("DELETE FROM bike_part_metric_snapshot")

        component_ids = [
            int(row[0])
            for row in self.conn.execute("SELECT component_catalog_id FROM component_catalog").fetchall()
        ]
        for component_catalog_id in component_ids:
            offer_rows = self.conn.execute(
                """
                SELECT price_value FROM offer_snapshot
                WHERE component_catalog_id = ? AND price_value IS NOT NULL
                """,
                (component_catalog_id,),
            ).fetchall()
            review_rows = self.conn.execute(
                """
                SELECT ra.rating_value
                FROM review_target rt
                JOIN review_article ra
                  ON ra.review_article_id = rt.review_article_id
                WHERE rt.component_catalog_id = ? AND ra.rating_value IS NOT NULL
                """,
                (component_catalog_id,),
            ).fetchall()
            offer_values = [float(row[0]) for row in offer_rows if row[0] is not None]
            review_values = [float(row[0]) for row in review_rows if row[0] is not None]
            avg_price = round(sum(offer_values) / len(offer_values), 2) if offer_values else None
            avg_rating = round(sum(review_values) / len(review_values), 2) if review_values else None
            quality_score = round(avg_rating / 5.0, 4) if avg_rating is not None else None
            value_score = round(quality_score / math.log1p(avg_price), 4) if avg_price and quality_score is not None else None
            confidence = round(min(1.0, (len(offer_values) + len(review_values)) / 8), 4)
            self.conn.execute(
                """
                INSERT INTO component_metric_snapshot(
                    component_catalog_id, snapshot_date, offer_count, review_count,
                    avg_price, avg_rating, price_score, quality_score, value_score, confidence_score, metric_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    component_catalog_id,
                    snapshot_date,
                    len(offer_values),
                    len(review_values),
                    avg_price,
                    avg_rating,
                    avg_price,
                    quality_score,
                    value_score,
                    confidence,
                    safe_json_text({}),
                ),
            )
            self.summary["component_metric_snapshot"] += 1

        component_metrics = {
            int(row["component_catalog_id"]): row
            for row in self.conn.execute(
                "SELECT * FROM component_metric_snapshot"
            ).fetchall()
        }
        grouped_components: dict[tuple[int, int], list[int]] = defaultdict(list)
        for row in self.conn.execute(
            """
            SELECT bike_variant_id, part_taxonomy_id, component_catalog_id
            FROM bike_build_component
            WHERE component_catalog_id IS NOT NULL
            """
        ).fetchall():
            grouped_components[(int(row["bike_variant_id"]), int(row["part_taxonomy_id"]))].append(
                int(row["component_catalog_id"])
            )

        for (bike_variant_id, part_taxonomy_id), component_ids in grouped_components.items():
            metrics = [component_metrics[cid] for cid in component_ids if cid in component_metrics]
            offer_count = sum(int(metric["offer_count"]) for metric in metrics)
            review_count = sum(int(metric["review_count"]) for metric in metrics)
            price_values = [float(metric["avg_price"]) for metric in metrics if metric["avg_price"] is not None]
            rating_values = [float(metric["avg_rating"]) for metric in metrics if metric["avg_rating"] is not None]
            avg_price = round(sum(price_values) / len(price_values), 2) if price_values else None
            avg_rating = round(sum(rating_values) / len(rating_values), 2) if rating_values else None
            quality_score = round(avg_rating / 5.0, 4) if avg_rating is not None else None
            value_score = round(quality_score / math.log1p(avg_price), 4) if avg_price and quality_score is not None else None
            confidence = round(min(1.0, (offer_count + review_count) / 8), 4)
            self.conn.execute(
                """
                INSERT INTO bike_part_metric_snapshot(
                    bike_variant_id, part_taxonomy_id, component_catalog_id, snapshot_date,
                    offer_count, review_count, avg_price, avg_rating, price_score, quality_score,
                    value_score, confidence_score, metric_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bike_variant_id,
                    part_taxonomy_id,
                    component_ids[0] if component_ids else None,
                    snapshot_date,
                    offer_count,
                    review_count,
                    avg_price,
                    avg_rating,
                    avg_price,
                    quality_score,
                    value_score,
                    confidence,
                    safe_json_text({}),
                ),
            )
            self.summary["bike_part_metric_snapshot"] += 1

    def build(self, general_db_path: Path, official_db_path: Path) -> dict[str, dict[str, int]]:
        self.seed_part_taxonomy()
        self.migrate_general_dataset_tables(general_db_path)
        self.migrate_open_dataset_artifacts()
        self.migrate_official_products(official_db_path)
        self.migrate_market_and_reviews(general_db_path, official_db_path)
        self.migrate_annotations()
        self.rebuild_metrics()
        self.conn.commit()
        counts = {}
        for table in [
            "source_system",
            "ingestion_run",
            "dataset",
            "dataset_version",
            "source_record",
            "dataset_annotation_record",
            "dataset_text_description",
            "dataset_feature_record",
            "media_asset",
            "part_taxonomy",
            "brand",
            "bike_variant",
            "bike_variant_alias",
            "component_catalog",
            "component_catalog_alias",
            "bike_build_component",
            "offer_snapshot",
            "review_article",
            "review_target",
            "image_item",
            "annotation_set",
            "annotated_object",
            "object_geometry",
            "component_metric_snapshot",
            "bike_part_metric_snapshot",
        ]:
            counts[table] = int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return {"inserted": dict(self.summary), "summary": counts}


def build_unified_warehouse(
    project_root: Path,
    general_db_path: Path,
    official_db_path: Path,
    unified_db_path: Path,
    schema_path: Path,
) -> dict[str, dict[str, int]]:
    if unified_db_path.exists():
        unified_db_path.unlink()
    conn = connect_db(unified_db_path)
    initialize_schema(conn, schema_path)
    builder = UnifiedWarehouseBuilder(project_root=project_root, conn=conn)
    result = builder.build(general_db_path=general_db_path, official_db_path=official_db_path)
    conn.close()
    return result
