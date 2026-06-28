from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from bike_data_platform.http_client import SimpleHttpClient


def _first_price(text: str) -> str | None:
    match = re.search(r"(\d[\d,\.]*\s?(?:€|£|\$|US\$))|((?:€|£|\$)\s?\d[\d,\.]*)", text)
    return match.group(0).strip() if match else None


def _looks_like_price_only(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return True
    return bool(re.fullmatch(r"(from\s+)?[\d,\.]+\s?(€|£|\$|US\$)?", compact))


def _extract_brand_from_url(href: str) -> str | None:
    path_parts = [part for part in urlparse(href).path.split("/") if part]
    if "en" in path_parts:
        idx = path_parts.index("en")
        if len(path_parts) > idx + 1:
            candidate = path_parts[idx + 1]
            if candidate not in {"components", "blog", "guides", "how-tos"}:
                return candidate
    return None


class BikeComponentsCollector:
    def __init__(self, user_agent: str, cache_dir):
        self.client = SimpleHttpClient(user_agent=user_agent, cache_dir=cache_dir, sleep_seconds=1.0)

    def fetch(self, url: str) -> list[dict[str, Any]]:
        text = self.client.get_text(url)
        soup = BeautifulSoup(text, "lxml")
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = urljoin(url, link["href"])
            title = " ".join(link.stripped_strings)
            if "/en/" not in href or href in seen:
                continue
            if "-p" not in href:
                continue
            if not title or len(title) < 5:
                continue
            if title.startswith("Rating:"):
                continue
            if _looks_like_price_only(title):
                continue
            if "read more" in title.lower():
                continue
            seen.add(href)

            rating_text = None
            parent_text = " ".join(link.parent.stripped_strings) if link.parent else title
            if "Rating:" in parent_text:
                rating_text = parent_text
            price_text = _first_price(parent_text) or _first_price(title)
            category = None
            if "/components/" in url:
                category = url.rstrip("/").split("/")[-1] or "components"
            manufacturer = _extract_brand_from_url(href)

            if price_text or rating_text or "/p" in href:
                rows.append(
                    {
                        "entity": "component",
                        "source": "bike_components",
                        "source_id": href,
                        "name": title,
                        "manufacturer": manufacturer,
                        "category": category,
                        "price_text": price_text,
                        "rating_text": rating_text,
                        "url": href,
                        "payload": {"context_url": url, "parent_text": parent_text[:1000]},
                    }
                )
        return rows


class BikeRadarCollector:
    def __init__(self, user_agent: str, cache_dir):
        self.client = SimpleHttpClient(user_agent=user_agent, cache_dir=cache_dir, sleep_seconds=1.0)

    def _find_review_object(self, payload: Any) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            payload_type = payload.get("@type")
            if payload_type == "Review":
                return payload
            if isinstance(payload_type, list) and "Review" in payload_type:
                return payload
            if "@graph" in payload:
                found = self._find_review_object(payload["@graph"])
                if found:
                    return found
            for value in payload.values():
                found = self._find_review_object(value)
                if found:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = self._find_review_object(item)
                if found:
                    return found
        return None

    def _fetch_review_detail(self, href: str) -> dict[str, Any]:
        text = self.client.get_text(href)
        soup = BeautifulSoup(text, "lxml")
        review_data: dict[str, Any] = {}
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.get_text(strip=True)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            review_obj = self._find_review_object(payload)
            if not review_obj:
                continue
            item_reviewed = review_obj.get("itemReviewed") or {}
            review_rating = review_obj.get("reviewRating") or {}
            rating_value = review_rating.get("ratingValue")
            rating_scale = review_rating.get("bestRating")
            review_data = {
                "headline": review_obj.get("headline") or review_obj.get("name"),
                "summary": review_obj.get("description")
                or item_reviewed.get("reviewBody")
                or item_reviewed.get("description"),
                "rating_value": float(rating_value) if rating_value is not None else None,
                "rating_scale": float(rating_scale) if rating_scale is not None else None,
                "reviewed_name": item_reviewed.get("name"),
                "reviewed_brand": item_reviewed.get("brand"),
                "reviewed_category": item_reviewed.get("category"),
                "image_url": (
                    item_reviewed.get("image", {}).get("url")
                    if isinstance(item_reviewed.get("image"), dict)
                    else None
                ),
            }
            break
        meta_description = soup.find("meta", attrs={"name": "description"})
        if meta_description and not review_data.get("summary"):
            review_data["summary"] = meta_description.get("content")
        review_data["detail_url"] = href
        return review_data

    def fetch(self, url: str) -> list[dict[str, Any]]:
        text = self.client.get_text(url)
        soup = BeautifulSoup(text, "lxml")
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = urljoin(url, link["href"])
            title = " ".join(link.stripped_strings)
            if "bikeradar.com" not in href or href in seen:
                continue
            if "/reviews/" not in href or not title or len(title) < 8:
                continue
            seen.add(href)
            detail = {}
            try:
                detail = self._fetch_review_detail(href)
            except Exception:
                detail = {}
            parent_text = " ".join(link.parent.stripped_strings) if link.parent else title
            summary = detail.get("summary")
            sibling_text = " ".join(link.next_siblings) if link.next_siblings else ""
            if sibling_text and not summary:
                summary = sibling_text.strip()[:500] or None
            price_text = _first_price(parent_text)

            parts = [part for part in href.split("/") if part]
            category = None
            subtype = None
            if "components" in parts:
                idx = parts.index("components")
                if len(parts) > idx + 1:
                    category = parts[idx + 1]
                if len(parts) > idx + 2:
                    subtype = parts[idx + 2]

            rows.append(
                {
                    "entity": "review",
                    "source": "bikeradar",
                    "source_id": href,
                    "title": detail.get("headline") or title,
                    "summary": summary,
                    "category": category,
                    "subtype": subtype,
                    "price_text": price_text,
                    "brand_hint": detail.get("reviewed_brand"),
                    "rating_value": detail.get("rating_value"),
                    "rating_scale": detail.get("rating_scale"),
                    "url": href,
                    "payload": {
                        "context_url": url,
                        "parent_text": parent_text[:1000],
                        "reviewed_name": detail.get("reviewed_name"),
                        "reviewed_brand": detail.get("reviewed_brand"),
                        "reviewed_category": detail.get("reviewed_category"),
                        "rating_value": detail.get("rating_value"),
                        "rating_scale": detail.get("rating_scale"),
                        "image_url": detail.get("image_url"),
                    },
                }
            )
        return rows
