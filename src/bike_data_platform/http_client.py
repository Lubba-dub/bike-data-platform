from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests


class SimpleHttpClient:
    def __init__(self, user_agent: str, cache_dir: Path | None = None, sleep_seconds: float = 1.0):
        self.user_agent = user_agent
        self.cache_dir = cache_dir
        self.sleep_seconds = sleep_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def _cache_path(self, key: str, suffix: str) -> Path | None:
        if not self.cache_dir:
            return None
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        prefix = "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in key[:48]).strip("._")
        safe_name = f"{prefix}_{digest}" if prefix else digest
        return self.cache_dir / f"{safe_name}{suffix}"

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        cache_key = f"json_{url}_{json.dumps(params or {}, sort_keys=True, ensure_ascii=False)}"
        cache_path = self._cache_path(cache_key, ".json")
        if cache_path and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        response = self.session.get(url, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(self.sleep_seconds)
        return payload

    def get_text(self, url: str) -> str:
        cache_key = f"text_{url}"
        cache_path = self._cache_path(cache_key, ".html")
        if cache_path and cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

        response = self.session.get(url, timeout=60)
        response.raise_for_status()
        text = response.text
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(text, encoding="utf-8")
        time.sleep(self.sleep_seconds)
        return text
