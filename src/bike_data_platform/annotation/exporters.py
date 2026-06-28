from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


def load_prefilter_rows(prefilter_csv_path: Path) -> list[dict]:
    with prefilter_csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def select_rows(rows: list[dict], allowed_decisions: set[str]) -> list[dict]:
    return [row for row in rows if row.get("prefilter_decision") in allowed_decisions]


def copy_selected_images(rows: list[dict], target_dir: Path) -> list[dict]:
    target_dir.mkdir(parents=True, exist_ok=True)
    exported_rows: list[dict] = []
    for row in rows:
        src_path = Path(row["absolute_image_path"])
        if not src_path.exists():
            continue
        safe_name = f'{row["source"]}_{row["source_id"]}{src_path.suffix.lower()}'
        dst_path = target_dir / safe_name
        shutil.copy2(src_path, dst_path)
        enriched = dict(row)
        enriched["exported_image_path"] = str(dst_path)
        enriched["exported_file_name"] = safe_name
        exported_rows.append(enriched)
    return exported_rows


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def build_label_list_file(output_path: Path, labels: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(labels), encoding="utf-8")
