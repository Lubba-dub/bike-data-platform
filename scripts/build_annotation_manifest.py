from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.annotation.manifest import collect_images, write_csv, write_label_studio_tasks


def main() -> None:
    image_root = ROOT / "data" / "raw" / "images"
    output_root = ROOT / "data" / "annotations" / "manifests"
    output_root.mkdir(parents=True, exist_ok=True)

    rows = collect_images(image_root)
    csv_path = output_root / "annotation_manifest.csv"
    tasks_path = output_root / "label_studio_tasks.json"

    if rows:
        write_csv(rows, csv_path)
        write_label_studio_tasks(rows, tasks_path)

    print(
        json.dumps(
            {
                "image_count": len(rows),
                "csv_path": str(csv_path),
                "label_studio_tasks": str(tasks_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
