from __future__ import annotations

from typing import Any

from bike_data_platform.http_client import SimpleHttpClient


class BikeIndexImageCollector:
    def __init__(self, base_url: str, user_agent: str, cache_dir, per_page: int = 50, max_pages: int = 5):
        self.base_url = base_url.rstrip("/")
        self.client = SimpleHttpClient(user_agent=user_agent, cache_dir=cache_dir, sleep_seconds=1.0)
        self.per_page = per_page
        self.max_pages = max_pages

    def collect(self, queries: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for query in queries:
            for page in range(1, self.max_pages + 1):
                payload = self.client.get_json(
                    f"{self.base_url}/search",
                    params={"query": query, "page": page, "per_page": self.per_page},
                )
                bikes = payload.get("bikes", [])
                if not bikes:
                    break
                for item in bikes:
                    image_url = item.get("large_img") or item.get("thumb")
                    if not image_url:
                        continue
                    rows.append(
                        {
                            "source": "bike_index",
                            "source_id": str(item.get("id")),
                            "query": query,
                            "title": item.get("title"),
                            "manufacturer_name": item.get("manufacturer_name"),
                            "frame_model": item.get("frame_model"),
                            "year": item.get("year"),
                            "description": item.get("description"),
                            "image_url": image_url,
                            "thumb_url": item.get("thumb"),
                            "page_url": item.get("url"),
                            "stolenness": item.get("stolenness"),
                            "license_note": "来源于 Bike Index 公开 API 记录，建议仅用于研究与标注筛选。",
                        }
                    )
        return rows


class WikimediaCommonsImageCollector:
    def __init__(self, user_agent: str, cache_dir, limit_per_query: int = 50):
        self.api_url = "https://commons.wikimedia.org/w/api.php"
        self.client = SimpleHttpClient(user_agent=user_agent, cache_dir=cache_dir, sleep_seconds=1.0)
        self.limit_per_query = limit_per_query

    def collect(self, queries: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for query in queries:
            payload = self.client.get_json(
                self.api_url,
                params={
                    "action": "query",
                    "format": "json",
                    "generator": "search",
                    "gsrsearch": f'filetype:bitmap {query}',
                    "gsrnamespace": 6,
                    "gsrlimit": self.limit_per_query,
                    "prop": "imageinfo|info",
                    "iiprop": "url|size|mime",
                    "inprop": "url"
                },
            )
            pages = payload.get("query", {}).get("pages", {})
            for page in pages.values():
                imageinfo = (page.get("imageinfo") or [{}])[0]
                image_url = imageinfo.get("url")
                if not image_url:
                    continue
                rows.append(
                    {
                        "source": "wikimedia_commons",
                        "source_id": str(page.get("pageid")),
                        "query": query,
                        "title": page.get("title"),
                        "manufacturer_name": None,
                        "frame_model": None,
                        "year": None,
                        "description": None,
                        "image_url": image_url,
                        "thumb_url": image_url,
                        "page_url": page.get("fullurl"),
                        "stolenness": None,
                        "license_note": "来源于 Wikimedia Commons，使用前请逐条核对原始授权。",
                    }
                )
        return rows
