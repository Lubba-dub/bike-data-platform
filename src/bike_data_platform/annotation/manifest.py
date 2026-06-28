from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def collect_images(image_root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(image_root.rglob("*")):
        if path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file():
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception:
            continue

        source = path.parts[-3] if len(path.parts) >= 3 else "unknown"
        rows.append(
            {
                "image_path": str(path),
                "file_name": path.name,
                "source": source,
                "width": width,
                "height": height,
                "annotate": 1,
                "quality_status": "pending",
                "view_label": "",
                "occlusion": "",
                "notes": "",
            }
        )
    return rows


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_label_studio_tasks(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tasks = [{"data": {"image": row["image_path"]}, "meta": row} for row in rows]
    output_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
