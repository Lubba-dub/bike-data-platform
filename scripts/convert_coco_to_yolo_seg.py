from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.annotation.coco_to_yolo import convert_coco_instance_segmentation


def main() -> None:
    parser = argparse.ArgumentParser(description="将 COCO 实例分割导出转换为 YOLOv8-seg 数据集")
    parser.add_argument("--coco", required=True, help="COCO annotations.json 路径")
    parser.add_argument("--images", required=True, help="原始图像根目录")
    parser.add_argument("--output", required=True, help="YOLO-seg 输出目录")
    parser.add_argument(
        "--classes",
        nargs="+",
        required=True,
        help="类别列表，如 frame front_wheel rear_wheel fork handlebar saddle drivetrain brake",
    )
    parser.add_argument("--train-ratio", type=float, default=0.8)
    args = parser.parse_args()

    result = convert_coco_instance_segmentation(
        coco_json_path=Path(args.coco),
        image_root=Path(args.images),
        output_root=Path(args.output),
        class_names=args.classes,
        train_ratio=args.train_ratio,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
