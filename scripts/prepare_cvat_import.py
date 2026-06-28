from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.annotation.exporters import (
    build_label_list_file,
    copy_selected_images,
    load_prefilter_rows,
    select_rows,
    write_csv,
    write_json,
)


DEFAULT_LABELS = [
    "frame",
    "front_wheel",
    "rear_wheel",
    "fork",
    "handlebar",
    "saddle",
    "drivetrain",
    "brake",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="生成可直接导入 CVAT 的自行车侧视图目录")
    parser.add_argument(
        "--include-review",
        action="store_true",
        help="除 keep 外，同时把 review 图片也导入 CVAT",
    )
    args = parser.parse_args()

    manifest_root = ROOT / "data" / "annotations" / "manifests"
    prefilter_csv = manifest_root / "bike_image_prefiltered.csv"
    output_root = ROOT / "data" / "annotations" / "cvat_import" / "side_view_dataset"
    image_dir = output_root / "images"

    rows = load_prefilter_rows(prefilter_csv)
    allowed = {"keep", "review"} if args.include_review else {"keep"}
    selected_rows = select_rows(rows, allowed)
    dropped_rows = select_rows(rows, {"drop"})
    exported_rows = copy_selected_images(selected_rows, image_dir)

    for idx, row in enumerate(exported_rows, start=1):
        row["cvat_id"] = idx
        row["cvat_status"] = "pending"
        row["annotate"] = 1

    kept_manifest_csv = output_root / "cvat_manifest.csv"
    kept_manifest_json = output_root / "cvat_manifest.json"
    dropped_manifest_csv = output_root / "excluded_drop_manifest.csv"
    labels_path = output_root / "labels.txt"
    note_path = output_root / "README.txt"

    write_csv(exported_rows, kept_manifest_csv)
    write_json(exported_rows, kept_manifest_json)
    write_csv(dropped_rows, dropped_manifest_csv)
    build_label_list_file(labels_path, DEFAULT_LABELS)
    note_path.write_text(
        "\n".join(
            [
                "CVAT 导入说明",
                "1. 将 images 文件夹中的图片导入 CVAT。",
                "2. 使用 labels.txt 中的标签创建 Polygon 标注任务。",
                "3. cvat_manifest.csv 记录了自动初筛分数与图片元数据。",
                "4. excluded_drop_manifest.csv 是已排除的非侧视图候选。",
            ]
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "selected": len(selected_rows),
                "exported": len(exported_rows),
                "dropped": len(dropped_rows),
                "image_dir": str(image_dir),
                "cvat_manifest_csv": str(kept_manifest_csv),
                "cvat_manifest_json": str(kept_manifest_json),
                "excluded_drop_manifest_csv": str(dropped_manifest_csv),
                "labels_path": str(labels_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
