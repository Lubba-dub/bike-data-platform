from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", SVG_NS)
ET.register_namespace("inkscape", INKSCAPE_NS)

MODE_META = {
    "price_score": {"label": "价格", "legendTitle": "价格热力图", "palette": "warm"},
    "quality_score": {"label": "质量", "legendTitle": "质量热力图", "palette": "cool"},
    "value_score": {"label": "性价比", "legendTitle": "性价比热力图", "palette": "teal"},
}

TEMPLATE_LABEL_MAP = {
    "frame": "frame",
    "fork": "fork",
    "saddle": "saddle",
    "seatpost": "seatpost",
    "seatpostclamp": "seatpost",
    "shockabsorber": "shock",
    "rearshockabsorber": "shock",
    "handlebar": "handlebar",
    "steamcap": "handlebar",
    "stemcap": "handlebar",
    "shiftlever": "shiftlever",
    "brakelever": "brake",
    "brake": "brake",
    "fronttire": "tire",
    "backtire": "tire",
    "frontrim": "tire",
    "backrim": "tire",
    "chainwheel": "chainwheel",
    "crank": "crank",
    "rearderailleur": "rearderailleur",
    "freewheel": "freewhile",
    "frontbrake": "brake",
    "padal": "pedal",
    "pedal": "pedal",
}

PART_FROM_API = {
    "tyre": ["tire"],
    "brake": ["brake"],
    "cassette": ["freewhile"],
    "wheel": ["tire"],
    "fork": ["fork"],
    "frame": ["frame"],
    "saddle": ["saddle"],
    "seatpost": ["seatpost"],
    "shock": ["shock"],
    "handlebar": ["handlebar"],
    "crankset": ["chainwheel", "crank"],
    "pedal": ["pedal"],
    "derailleur": ["rearderailleur"],
    "shifter": ["shiftlever"],
    "chain": ["chainwheel"],
}

TEMPLATE_VARIANTS = {
    "road": {
        "label": "公路车模板",
        "description": "更适合公路、耐力、砾石与折叠车型的细长几何结构。",
        "accent": "#356dce",
        "svg_path": ROOT / "img_svg_templete" / "公路车各部件分离模板.svg",
    },
    "mountain": {
        "label": "山地车模板",
        "description": "更适合山地、越野、林道与长避震车架结构。",
        "accent": "#2c8a5a",
        "svg_path": ROOT / "img_svg_templete" / "山地车各部分分离模板.svg",
    },
}

THEME_PRESETS = {
    "palettes": {
        "warm": ["#fff6ef", "#f7b37a", "#e85b3a", "#991f17"],
        "cool": ["#eef6ff", "#8eb7ff", "#3d6ef7", "#15308a"],
        "teal": ["#effcf8", "#8be0cb", "#22b8a2", "#0d6b66"],
        "mono": ["#f4f4f4", "#cfcfcf", "#8a8a8a", "#3f3f3f"],
    },
    "missing": {"fill": "#d9dde3", "stroke": "#a0a7b4", "opacity": 0.45},
    "legend": {"position": "bottom-right", "showEvidenceLayer": True},
}


def _normalize_svg_token(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def resolve_template_part_label(value: str | None) -> str | None:
    normalized = _normalize_svg_token(value)
    direct = TEMPLATE_LABEL_MAP.get(normalized)
    if direct:
        return direct
    for prefix, mapped in TEMPLATE_LABEL_MAP.items():
        if normalized.startswith(prefix):
            return mapped
    return None


def _parse_style(style_text: str | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not style_text:
        return parsed
    for chunk in style_text.split(";"):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _serialize_style(style_map: dict[str, str]) -> str:
    return ";".join(f"{key}:{value}" for key, value in style_map.items())


def build_template_id_map(template_svg_path: Path) -> dict[str, list[str]]:
    root = ET.parse(template_svg_path).getroot()
    part_map: dict[str, list[str]] = {}
    for el in root.iter():
        raw_label = el.attrib.get(f"{{{INKSCAPE_NS}}}label") or el.attrib.get("id")
        part_label = resolve_template_part_label(raw_label)
        element_id = el.attrib.get("id")
        if part_label and element_id:
            part_map.setdefault(part_label, [])
            if element_id not in part_map[part_label]:
                part_map[part_label].append(element_id)
    return part_map


def collect_svg_element_ids(template_svg_path: Path) -> list[str]:
    root = ET.parse(template_svg_path).getroot()
    ids: list[str] = []
    for el in root.iter():
        element_id = el.attrib.get("id")
        if element_id and element_id not in ids:
            ids.append(element_id)
    return ids


def build_neutral_template_svg(template_svg_path: Path) -> str:
    tree = ET.parse(template_svg_path)
    root = tree.getroot()
    target_tags = {
        f"{{{SVG_NS}}}path",
        f"{{{SVG_NS}}}ellipse",
        f"{{{SVG_NS}}}circle",
        f"{{{SVG_NS}}}polygon",
        f"{{{SVG_NS}}}rect",
        f"{{{SVG_NS}}}line",
    }
    for el in root.iter():
        if el.tag not in target_tags:
            continue
        style = _parse_style(el.attrib.get("style"))
        if el.tag.endswith("line"):
            style["stroke"] = "#d0d0d0"
            style.setdefault("stroke-width", "1.4")
        else:
            style["fill"] = "#d8d8d8"
            style.setdefault("stroke", "#bcbcbc")
            style.setdefault("stroke-width", "0.969463")
        el.set("style", _serialize_style(style))
    return ET.tostring(root, encoding="unicode")


def _supported_parts(id_map: dict[str, list[str]]) -> list[str]:
    return sorted(id_map.keys())


def build_template_package(template_type: str, example_bike: dict | None = None) -> dict:
    variant = TEMPLATE_VARIANTS[template_type]
    id_map = build_template_id_map(variant["svg_path"])
    all_element_ids = collect_svg_element_ids(variant["svg_path"])
    mapped_ids = {element_id for ids in id_map.values() for element_id in ids}
    package = {
        "name": f"@bike-templates/{template_type}-template",
        "version": "1.0.0",
        "templateType": template_type,
        "title": variant["label"],
        "description": variant["description"],
        "engineVersion": ">=1.0.0",
        "accent": variant["accent"],
        "supportedParts": _supported_parts(id_map),
        "requiredParts": ["frame", "fork", "tire"],
        "optionalParts": [part for part in _supported_parts(id_map) if part not in {"frame", "fork", "tire"}],
        "supportedModes": list(MODE_META.keys()),
        "svgPath": str(variant["svg_path"]),
        "svgBase": build_neutral_template_svg(variant["svg_path"]),
        "mapping": id_map,
        "allElementIds": all_element_ids,
        "unboundElementIds": [element_id for element_id in all_element_ids if element_id not in mapped_ids],
        "theme": THEME_PRESETS,
        "schema": {
            "requiredParts": ["frame", "fork", "tire"],
            "optionalParts": [part for part in _supported_parts(id_map) if part not in {"frame", "fork", "tire"}],
            "requiredModes": ["price_score"],
            "optionalModes": ["quality_score", "value_score"],
        },
        "exampleBike": example_bike,
    }
    return package


def load_template_packages(example_bikes: dict[str, dict] | None = None) -> dict[str, dict]:
    packages: dict[str, dict] = {}
    for template_type in TEMPLATE_VARIANTS:
        packages[template_type] = build_template_package(
            template_type,
            example_bike=(example_bikes or {}).get(template_type),
        )
    return packages


def write_template_package_artifacts(output_dir: Path, template_packages: dict[str, dict]) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for template_type, package in template_packages.items():
        package_dir = output_dir / template_type
        package_dir.mkdir(parents=True, exist_ok=True)
        svg_path = Path(package["svgPath"])
        mapping_path = package_dir / "mapping.json"
        theme_path = package_dir / "theme.json"
        schema_path = package_dir / "schema.json"
        package_json_path = package_dir / "package.json"
        example_path = package_dir / "example-bike.json"
        neutral_svg_path = package_dir / "template.svg"
        preview_path = package_dir / "preview.svg"

        package_json = {
            "name": package["name"],
            "version": package["version"],
            "templateType": package["templateType"],
            "title": package["title"],
            "description": package["description"],
            "engineVersion": package["engineVersion"],
            "accent": package["accent"],
            "supportedParts": package["supportedParts"],
            "supportedModes": package["supportedModes"],
        }

        package_json_path.write_text(json.dumps(package_json, ensure_ascii=False, indent=2), encoding="utf-8")
        mapping_path.write_text(json.dumps(package["mapping"], ensure_ascii=False, indent=2), encoding="utf-8")
        theme_path.write_text(json.dumps(package["theme"], ensure_ascii=False, indent=2), encoding="utf-8")
        schema_path.write_text(json.dumps(package["schema"], ensure_ascii=False, indent=2), encoding="utf-8")
        neutral_svg_path.write_text(package["svgBase"], encoding="utf-8")
        preview_path.write_text(svg_path.read_text(encoding="utf-8"), encoding="utf-8")
        if package.get("exampleBike") is not None:
            example_path.write_text(json.dumps(package["exampleBike"], ensure_ascii=False, indent=2), encoding="utf-8")

        written.extend(
            [
                str(package_json_path),
                str(mapping_path),
                str(theme_path),
                str(schema_path),
                str(neutral_svg_path),
                str(preview_path),
            ]
        )
    return written
