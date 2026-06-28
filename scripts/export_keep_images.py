from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.annotation.exporters import copy_selected_images, load_prefilter_rows, select_rows, write_csv, write_json


def main() -> None:
    manifest_root = ROOT / "data" / "annotations" / "manifests"
    prefilter_csv = manifest_root / "bike_image_prefiltered.csv"
    output_root = ROOT / "data" / "annotations" / "exports" / "keep_images"
    image_dir = output_root / "images"

    rows = load_prefilter_rows(prefilter_csv)
    keep_rows = select_rows(rows, {"keep"})
    exported_rows = copy_selected_images(keep_rows, image_dir)

    csv_path = output_root / "keep_manifest.csv"
    json_path = output_root / "keep_manifest.json"
    write_csv(exported_rows, csv_path)
    write_json(exported_rows, json_path)

    print(
        json.dumps(
            {
                "selected": len(keep_rows),
                "exported": len(exported_rows),
                "image_dir": str(image_dir),
                "csv_path": str(csv_path),
                "json_path": str(json_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
