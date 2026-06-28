from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bike_data_platform.datasets import download_bbbicycles, download_delftbikes, download_geobiked
from bike_data_platform.settings import get_settings


def main() -> None:
    settings = get_settings()
    datasets = settings.config["datasets"]
    results = []

    delftbikes_dir = settings.raw_datasets_dir / "delftbikes"
    results.append(download_delftbikes(delftbikes_dir, datasets["delftbikes"]["landing_page"]))

    bbb_dir = settings.raw_datasets_dir / "bbbicycles"
    results.append(
        download_bbbicycles(
            bbb_dir,
            datasets["bbbicycles"]["hf_repo_id"],
            datasets["bbbicycles"].get("repo_type", "dataset"),
        )
    )

    geobiked_dir = settings.raw_datasets_dir / "geobiked"
    results.append(
        download_geobiked(
            geobiked_dir,
            datasets["geobiked"]["repo"],
            datasets["geobiked"]["gdrive_folder"],
        )
    )

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
