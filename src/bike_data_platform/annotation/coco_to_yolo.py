from __future__ import annotations

import json
import random
import shutil
from collections import defaultdict
from pathlib import Path

import yaml


def _polygon_to_yolo(points: list[float], width: int, height: int) -> str | None:
    if len(points) < 6 or len(points) % 2 != 0:
        return None
    values = []
    for idx, value in enumerate(points):
        if idx % 2 == 0:
            values.append(value / width)
        else:
            values.append(value / height)
    return " ".join(f"{v:.6f}" for v in values)


def convert_coco_instance_segmentation(
    coco_json_path: Path,
    image_root: Path,
    output_root: Path,
    class_names: list[str],
    train_ratio: float = 0.8,
    seed: int = 42,
) -> dict:
    payload = json.loads(coco_json_path.read_text(encoding="utf-8"))
    categories = {cat["id"]: cat["name"] for cat in payload["categories"]}
    class_map = {name: idx for idx, name in enumerate(class_names)}

    image_records = {img["id"]: img for img in payload["images"]}
    annotations_by_image: dict[int, list[dict]] = defaultdict(list)
    for ann in payload["annotations"]:
        annotations_by_image[ann["image_id"]].append(ann)

    image_ids = list(image_records.keys())
    random.Random(seed).shuffle(image_ids)
    split_index = int(len(image_ids) * train_ratio)
    train_ids = set(image_ids[:split_index])

    for split in ["train", "val"]:
        (output_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_root / "labels" / split).mkdir(parents=True, exist_ok=True)

    converted_images = 0
    converted_labels = 0

    for image_id, image_info in image_records.items():
        split = "train" if image_id in train_ids else "val"
        file_name = image_info["file_name"]
        width = image_info["width"]
        height = image_info["height"]
        src_path = image_root / file_name
        if not src_path.exists():
            continue
        dst_image_path = output_root / "images" / split / Path(file_name).name
        shutil.copy2(src_path, dst_image_path)
        converted_images += 1

        label_lines: list[str] = []
        for ann in annotations_by_image.get(image_id, []):
            category_name = categories.get(ann["category_id"])
            if category_name not in class_map:
                continue
            segmentation = ann.get("segmentation") or []
            if not isinstance(segmentation, list):
                continue
            for polygon in segmentation:
                line = _polygon_to_yolo(polygon, width, height)
                if line:
                    label_lines.append(f"{class_map[category_name]} {line}")
                    converted_labels += 1

        label_path = output_root / "labels" / split / f"{Path(file_name).stem}.txt"
        label_path.write_text("\n".join(label_lines), encoding="utf-8")

    dataset_yaml = {
        "path": str(output_root),
        "train": "images/train",
        "val": "images/val",
        "names": {idx: name for idx, name in enumerate(class_names)},
    }
    (output_root / "data.yaml").write_text(yaml.safe_dump(dataset_yaml, allow_unicode=True, sort_keys=False), encoding="utf-8")

    return {
        "converted_images": converted_images,
        "converted_labels": converted_labels,
        "class_count": len(class_names),
        "output_root": str(output_root),
    }
