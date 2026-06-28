from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.annotation.silhouette import (
    generate_silhouette_from_file,
    write_silhouette_manifest,
)


def iter_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    patterns = ("*.jpg", "*.jpeg", "*.png", "*.webp")
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(input_path.rglob(pattern)))
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="将白底自行车图片自动处理为黑色剪影和二值掩膜")
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data" / "raw" / "images",
        help="输入图片文件或目录",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "annotations" / "exports" / "white_silhouettes",
        help="输出目录",
    )
    parser.add_argument("--white-threshold", type=int, default=245)
    parser.add_argument("--diff-threshold", type=int, default=18)
    parser.add_argument("--min-area", type=int, default=512)
    parser.add_argument("--crop", action="store_true", help="输出时按前景 bbox 裁切")
    parser.add_argument("--limit", type=int, default=0, help="限制处理图片数量，0 表示不限制")
    args = parser.parse_args()

    files = iter_input_files(args.input)
    if args.limit > 0:
        files = files[: args.limit]

    rows = []
    failures = []
    for file_path in files:
        try:
            rows.append(
                generate_silhouette_from_file(
                    input_path=file_path,
                    output_dir=args.output,
                    white_threshold=args.white_threshold,
                    diff_threshold=args.diff_threshold,
                    min_area=args.min_area,
                    crop=args.crop,
                )
            )
        except Exception as exc:
            failures.append({"input_path": str(file_path), "error": str(exc)})

    manifest_path = args.output / "silhouette_manifest.json"
    failures_path = args.output / "silhouette_failures.json"
    write_silhouette_manifest(rows, manifest_path)
    failures_path.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "input": str(args.input),
                "output": str(args.output),
                "processed": len(rows),
                "failed": len(failures),
                "manifest_path": str(manifest_path),
                "failures_path": str(failures_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
