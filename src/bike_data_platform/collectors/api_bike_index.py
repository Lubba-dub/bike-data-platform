from __future__ import annotations

from typing import Any

from bike_data_platform.http_client import SimpleHttpClient


class BikeIndexCollector:
    def __init__(self, base_url: str, user_agent: str, cache_dir, per_page: int = 25, max_pages: int = 3):
        self.base_url = base_url.rstrip("/")
        self.client = SimpleHttpClient(user_agent=user_agent, cache_dir=cache_dir, sleep_seconds=1.0)
        self.per_page = per_page
        self.max_pages = max_pages

    def fetch_manufacturers(self) -> list[dict[str, Any]]:
        payload = self.client.get_json(f"{self.base_url}/manufacturers", params={"page": 1, "per_page": 100})
        rows: list[dict[str, Any]] = []
        for item in payload.get("manufacturers", []):
            rows.append(
                {
                    "entity": "manufacturer",
                    "source": "bike_index",
                    "source_id": str(item.get("id")),
                    "name": item.get("name"),
                    "slug": item.get("slug"),
                    "url": item.get("url"),
                    "payload": item,
                }
            )
        return rows

    def search_bikes(self, query: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, self.max_pages + 1):
            payload = self.client.get_json(
                f"{self.base_url}/search",
                params={"query": query, "page": page, "per_page": self.per_page},
            )
            bikes = payload.get("bikes", [])
            if not bikes:
                break
            for item in bikes:
                rows.append(
                    {
                        "entity": "bike",
                        "source": "bike_index",
                        "source_id": str(item.get("id")),
                        "query": query,
                        "title": item.get("title"),
                        "manufacturer_name": item.get("manufacturer_name"),
                        "frame_model": item.get("frame_model"),
                        "year": item.get("year"),
                        "description": item.get("description"),
                        "thumb": item.get("thumb"),
                        "large_img": item.get("large_img"),
                        "url": item.get("url"),
                        "stolenness": item.get("stolenness"),
                        "payload": item,
                    }
                )
        return rows
