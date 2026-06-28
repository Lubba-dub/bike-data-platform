from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from huggingface_hub import hf_hub_download, snapshot_download


def _write_manifest(target_dir: Path, manifest: dict) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def download_delftbikes(target_dir: Path, landing_page: str) -> dict:
    target_dir.mkdir(parents=True, exist_ok=True)
    response = requests.get(landing_page, timeout=60)
    response.raise_for_status()
    html = response.text
    (target_dir / "landing_page.html").write_text(html, encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    download_links = []
    for link in soup.find_all("a", href=True):
        href = urljoin(landing_page, link["href"])
        if "/file/" in href or re.search(r"\.(zip|json|csv|jpg|png)$", href, flags=re.I):
            download_links.append(href)

    manifest = {
        "dataset_name": "delftbikes",
        "source_url": landing_page,
        "status": "metadata_downloaded",
        "download_links": sorted(set(download_links)),
        "downloaded_at": datetime.now(UTC).isoformat(),
    }
    _write_manifest(target_dir, manifest)
    return manifest


def download_bbbicycles(target_dir: Path, repo_id: str, repo_type: str = "dataset") -> dict:
    target_dir.mkdir(parents=True, exist_ok=True)
    readme_path = hf_hub_download(
        repo_id=repo_id,
        repo_type=repo_type,
        filename="README.md",
        local_dir=target_dir,
    )
    full_download = os.getenv("BBBICYCLES_FULL_DOWNLOAD", "0") == "1"
    manifest = {
        "dataset_name": "bbbicycles",
        "source_url": f"https://huggingface.co/datasets/{repo_id}",
        "readme_path": readme_path,
        "downloaded_at": datetime.now(UTC).isoformat(),
    }
    if full_download:
        local_path = snapshot_download(
            repo_id=repo_id,
            repo_type=repo_type,
            local_dir=target_dir,
        )
        manifest["status"] = "downloaded"
        manifest["local_path"] = local_path
    else:
        manifest["status"] = "metadata_only"
        manifest["detail"] = "设置环境变量 BBBICYCLES_FULL_DOWNLOAD=1 后可执行全量下载。数据集体量约 104GB。"
    _write_manifest(target_dir, manifest)
    return manifest


def download_geobiked(target_dir: Path, repo: str, gdrive_folder: str) -> dict:
    target_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = target_dir / "repo"
    if not repo_dir.exists():
        subprocess.run(["git", "clone", repo, str(repo_dir)], check=True)

    enable_gdown = os.getenv("GEOBIKED_GDOWN", "0") == "1"
    drive_dir = target_dir / "gdrive"
    drive_dir.mkdir(parents=True, exist_ok=True)
    if enable_gdown:
        gdown_cmd = [
            "python",
            "-m",
            "gdown",
            "--folder",
            gdrive_folder,
            "-O",
            str(drive_dir),
        ]
        result = subprocess.run(gdown_cmd, capture_output=True, text=True)
        status = "downloaded" if result.returncode == 0 else "partial"
        stdout = result.stdout[-4000:]
        stderr = result.stderr[-4000:]
    else:
        status = "repo_only"
        stdout = ""
        stderr = "设置环境变量 GEOBIKED_GDOWN=1 后可尝试下载 Google Drive 数据文件。"
    manifest = {
        "dataset_name": "geobiked",
        "source_url": gdrive_folder,
        "status": status,
        "repo": repo,
        "repo_dir": str(repo_dir),
        "gdrive_dir": str(drive_dir),
        "gdown_stdout": stdout,
        "gdown_stderr": stderr,
        "downloaded_at": datetime.now(UTC).isoformat(),
    }
    _write_manifest(target_dir, manifest)
    return manifest
