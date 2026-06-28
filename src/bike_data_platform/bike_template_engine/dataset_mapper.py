from __future__ import annotations

from typing import Any

from .protocol import EngineBikePayload, EnginePartPayload, EvidencePayload
from .template_package import MODE_META, PART_FROM_API, TEMPLATE_VARIANTS


def slugify_text(value: str) -> str:
    lowered = value.lower()
    normalized = "".join(ch if ch.isalnum() else "-" for ch in lowered)
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-")


def infer_bike_type_from_record(record: dict[str, Any]) -> str:
    explicit = str(record.get("bike_type") or "").strip().lower()
    if explicit:
        return explicit
    text = " ".join(
        str(record.get(key) or "")
        for key in ("bike_name", "brand", "description", "official_url", "bikeType")
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
            "slash",
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
            "habit",
            "scalpel",
            "jekyll",
            "moterra",
        )
    ):
        return "mountain"
    if any(token in text for token in ("gravel", "silex")):
        return "gravel"
    if any(token in text for token in ("road", "race", "endurance", "aero", "endurace", "madone", "domane")):
        return "road"
    if any(token in text for token in ("city", "urban", "commuter", "hybrid", "touring")):
        return "city"
    if any(token in text for token in ("electric", "e-bike", "ebike")):
        return "electric"
    return "other"


def template_type_for_bike_type(bike_type: str) -> str:
    return "mountain" if bike_type == "mountain" else "road"


def _part_display_name(part_key: str) -> str:
    return {
        "frame": "Frame",
        "fork": "Fork",
        "brake": "Brake",
        "tyre": "Tyre",
        "tire": "Tire",
        "seatpost": "Seatpost",
        "shock": "Shock",
        "derailleur": "Rear Derailleur",
        "cassette": "Cassette",
        "handlebar": "Handlebar",
        "saddle": "Saddle",
        "pedal": "Pedal",
        "shifter": "Shift Lever",
        "crankset": "Crankset",
        "chain": "Chain",
    }.get(part_key, part_key.replace("_", " ").title())


def _source_type_from_part(part: dict[str, Any]) -> str:
    spec_name = str(part.get("spec_name") or "").lower()
    if "representative fallback" in spec_name:
        return "representative"
    if "fallback" in spec_name or bool(part.get("is_inferred")):
        return "inferred"
    return "observed"


def _coverage_from_counts(offers: int, reviews: int) -> str:
    total = offers + reviews
    if total >= 8:
        return "high"
    if total >= 3:
        return "medium"
    return "low"


def _confidence_from_counts(offers: int, reviews: int) -> float:
    return round(min(0.96, 0.6 + 0.025 * min(6, offers) + 0.02 * min(8, reviews)), 2)


def build_engine_payload_from_bike(bike: dict[str, Any]) -> dict[str, Any]:
    bike_name = str(bike.get("bike_name") or bike.get("bikeName") or "Bike")
    brand = str(bike.get("brand") or "unknown")
    bike_type = infer_bike_type_from_record(bike)
    template_type = str(bike.get("templateType") or template_type_for_bike_type(bike_type))
    engine_parts: list[EnginePartPayload] = []
    mapped_parts_count = 0

    for part in bike.get("parts", []):
        part_key = str(part.get("part_key") or part.get("partKey") or "").lower()
        if not part_key:
            continue
        template_labels = list(PART_FROM_API.get(part_key, []))
        render_status = "mapped" if template_labels else "template_missing"
        if template_labels:
            mapped_parts_count += 1
        offers_count = int(part.get("offers_count") or part.get("offersCount") or 0)
        reviews_count = int(part.get("reviews_count") or part.get("reviewsCount") or 0)
        metrics = {
            mode: part.get(mode)
            for mode in MODE_META
        }
        engine_parts.append(
            EnginePartPayload(
                partKey=part_key,
                displayName=_part_display_name(part_key),
                templateLabels=template_labels,
                componentName=part.get("component_name") or part.get("componentName") or part.get("value"),
                brandHint=part.get("brand_hint") or part.get("brandHint"),
                sourceType=_source_type_from_part(part),
                evidence=EvidencePayload(
                    offersCount=offers_count,
                    reviewsCount=reviews_count,
                    confidence=_confidence_from_counts(offers_count, reviews_count),
                    coverage=_coverage_from_counts(offers_count, reviews_count),
                ),
                metrics=metrics,
                meta={
                    "spec_name": part.get("spec_name"),
                    "slot": part.get("slot"),
                },
            )
        )

    payload = EngineBikePayload(
        schemaVersion="1.0.0",
        bikeId=str(bike.get("bikeId") or slugify_text(f"{brand}-{bike_name}")),
        bikeName=bike_name,
        brand=brand,
        bikeType=bike_type,
        templateType=template_type if template_type in TEMPLATE_VARIANTS else template_type_for_bike_type(bike_type),
        views=bike.get("views") or {"front": None, "side": None, "rear": None},
        availableModes=list(MODE_META.keys()),
        defaultMode="price_score",
        parts=engine_parts,
        summary={
            "partsCount": len(engine_parts),
            "mappedPartsCount": mapped_parts_count,
            "templateCoverage": round(mapped_parts_count / max(1, len(engine_parts)), 2),
            "evidenceScore": round(
                sum(part.evidence.offersCount + part.evidence.reviewsCount for part in engine_parts) / max(1, len(engine_parts)),
                2,
            ),
            "hasPhoto": bool((bike.get("views") or {}).get("side")),
        },
        meta={
            "source": bike.get("source") or "website_bikes_api",
            "description": bike.get("description"),
            "officialUrl": bike.get("official_url") or bike.get("officialUrl"),
        },
    )
    return payload.to_dict()


def _lookup_value(record: dict[str, Any], path: str | None) -> Any:
    if not path:
        return None
    current: Any = record
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def map_generic_dataset(records: list[dict[str, Any]], rule_set: dict[str, Any]) -> list[dict[str, Any]]:
    part_aliases = {str(key).lower(): str(value).lower() for key, value in (rule_set.get("partMappings") or {}).items()}
    metric_mappings = rule_set.get("metricMappings") or {}
    mapped_bikes: list[dict[str, Any]] = []
    for record in records:
        bike_name = _lookup_value(record, rule_set.get("bikeNameField")) or "External Bike"
        brand = _lookup_value(record, rule_set.get("brandField")) or "external"
        bike_type = _lookup_value(record, rule_set.get("bikeTypeField")) or infer_bike_type_from_record(record)
        template_type = template_type_for_bike_type(str(bike_type).lower())
        raw_parts = _lookup_value(record, rule_set.get("partsPath")) or []
        parts = []
        for part in raw_parts:
            raw_key = str(_lookup_value(part, rule_set.get("partKeyField")) or part.get("part_key") or "").lower()
            part_key = part_aliases.get(raw_key, raw_key)
            if not part_key:
                continue
            metrics = {
                mode: _lookup_value(part, source_path)
                for mode, source_path in metric_mappings.items()
            }
            parts.append(
                {
                    "part_key": part_key,
                    "component_name": _lookup_value(part, rule_set.get("componentNameField")) or part.get("component_name"),
                    "brand_hint": _lookup_value(part, rule_set.get("brandHintField")) or part.get("brand_hint"),
                    "offers_count": _lookup_value(part, rule_set.get("offersCountField")) or part.get("offers_count") or 0,
                    "reviews_count": _lookup_value(part, rule_set.get("reviewsCountField")) or part.get("reviews_count") or 0,
                    **metrics,
                }
            )
        mapped_bikes.append(
            build_engine_payload_from_bike(
                {
                    "bike_name": bike_name,
                    "brand": brand,
                    "bike_type": bike_type,
                    "templateType": template_type,
                    "views": {
                        "front": None,
                        "side": _lookup_value(record, rule_set.get("sideViewField")),
                        "rear": None,
                    },
                    "parts": parts,
                    "source": rule_set.get("sourceName") or "generic",
                    "description": _lookup_value(record, rule_set.get("descriptionField")),
                    "official_url": _lookup_value(record, rule_set.get("officialUrlField")),
                }
            )
        )
    return mapped_bikes
