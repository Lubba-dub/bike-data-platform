from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.annotation.prefilter import score_side_view_candidate


def main() -> None:
    manifest_root = ROOT / "data" / "annotations" / "manifests"
    input_json = manifest_root / "bike_image_candidates.json"
    output_json = manifest_root / "bike_image_prefiltered.json"
    output_csv = manifest_root / "bike_image_prefiltered.csv"

    rows = json.loads(input_json.read_text(encoding="utf-8"))
    scored_rows = []
    for row in rows:
        if not row.get("downloaded"):
            continue
        result = score_side_view_candidate(row)
        enriched = dict(row)
        enriched.update(
            {
                "prefilter_score": result.score,
                "prefilter_decision": result.decision,
                "prefilter_reasons": " | ".join(result.reasons),
                "width": result.width,
                "height": result.height,
                "aspect_ratio": result.aspect_ratio,
                "edge_box_ratio_w": result.edge_box_ratio_w,
                "edge_box_ratio_h": result.edge_box_ratio_h,
                "edge_box_aspect": result.edge_box_aspect,
                "edge_density": result.edge_density,
            }
        )
        scored_rows.append(enriched)

    scored_rows.sort(key=lambda x: (x["prefilter_decision"] != "keep", -x["prefilter_score"]))
    output_json.write_text(json.dumps(scored_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    if scored_rows:
        with output_csv.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(scored_rows[0].keys()))
            writer.writeheader()
            writer.writerows(scored_rows)

    summary = {
        "total": len(scored_rows),
        "keep": sum(1 for row in scored_rows if row["prefilter_decision"] == "keep"),
        "review": sum(1 for row in scored_rows if row["prefilter_decision"] == "review"),
        "drop": sum(1 for row in scored_rows if row["prefilter_decision"] == "drop"),
        "json_path": str(output_json),
        "csv_path": str(output_csv),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
