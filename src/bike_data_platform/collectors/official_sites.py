from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from bike_data_platform.http_client import SimpleHttpClient


IMAGE_SIDE_HINTS = ("side", "profile", "lateral")
IMAGE_FRONT_HINTS = ("front", "headon")
IMAGE_REAR_HINTS = ("rear", "back")

COMPONENT_KEYWORDS = (
    "frame",
    "fork",
    "shock",
    "derailleur",
    "brake",
    "cassette",
    "chain",
    "crank",
    "wheel",
    "tyre",
    "tire",
    "groupset",
    "battery",
    "motor",
    "hub",
    "saddle",
    "seatpost",
    "handlebar",
)

NON_PRODUCT_IMAGE_HINTS = (
    "icon",
    "logo",
    "sprite",
    "badge",
    "arrow",
    "menu",
    "banner",
    "placeholder",
    "loading",
    "thumb",
)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_url(base_url: str, href: str) -> str | None:
    if not href:
        return None
    if href.startswith("mailto:") or href.startswith("javascript:"):
        return None
    url = urljoin(base_url, href)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    return url.split("#")[0]


def _is_likely_image(url: str) -> bool:
    lower = url.lower()
    return any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"))


def _looks_like_product_image(url: str) -> bool:
    lower = url.lower()
    if not _is_likely_image(lower):
        return False
    if any(hint in lower for hint in NON_PRODUCT_IMAGE_HINTS):
        return False
    return True


def _extract_price_text(text: str) -> str | None:
    match = re.search(r"(€|£|\$|US\$|SG\$)\s?[\d\.,]+", text)
    return match.group(0) if match else None


def _extract_json_ld_products(soup: BeautifulSoup) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates: list[Any]
        if isinstance(payload, list):
            candidates = payload
        else:
            candidates = [payload]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            typ = str(item.get("@type", "")).lower()
            if "product" in typ:
                rows.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, dict) and "product" in str(node.get("@type", "")).lower():
                        rows.append(node)
    return rows


def _classify_images(image_urls: list[str]) -> dict[str, str | None]:
    image_urls = [url for url in image_urls if _looks_like_product_image(url)]
    side = None
    front = None
    rear = None
    for url in image_urls:
        lower = url.lower()
        if not side and any(hint in lower for hint in IMAGE_SIDE_HINTS):
            side = url
        if not front and any(hint in lower for hint in IMAGE_FRONT_HINTS):
            front = url
        if not rear and any(hint in lower for hint in IMAGE_REAR_HINTS):
            rear = url
    if image_urls:
        side = side or image_urls[0]
        front = front or (image_urls[1] if len(image_urls) > 1 else image_urls[0])
        rear = rear or (image_urls[2] if len(image_urls) > 2 else image_urls[-1])
    return {"front_view_url": front, "side_view_url": side, "rear_view_url": rear}


def _extract_specs_from_markdownish_lines(text: str) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line or "：" not in line and ":" not in line:
            continue
        line = line.lstrip("-").strip()
        separator = "：" if "：" in line else ":"
        key, value = line.split(separator, 1)
        key = _clean_text(key)
        value = _clean_text(value)
        if key and value:
            specs.append({"name": key, "value": value})
    return specs


def _extract_specs_from_tables(soup: BeautifulSoup) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            key = _clean_text(cells[0].get_text(" ", strip=True))
            value = _clean_text(cells[1].get_text(" ", strip=True))
            if key and value:
                specs.append({"name": key, "value": value})

    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            key = _clean_text(dt.get_text(" ", strip=True))
            value = _clean_text(dd.get_text(" ", strip=True))
            if key and value:
                specs.append({"name": key, "value": value})

    return specs


def _extract_specs_from_text(soup: BeautifulSoup) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for li in soup.find_all("li"):
        text = _clean_text(li.get_text(" ", strip=True))
        if len(text) < 4:
            continue
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key = _clean_text(key)
        value = _clean_text(value)
        if not key or not value:
            continue
        if any(keyword in key.lower() for keyword in COMPONENT_KEYWORDS):
            specs.append({"name": key, "value": value})
    return specs


def _extract_components(specs: list[dict[str, str]]) -> list[dict[str, str]]:
    components = []
    for item in specs:
        key = item["name"].lower()
        if any(keyword in key for keyword in COMPONENT_KEYWORDS):
            components.append(item)
    return components


@dataclass
class BrandCrawler:
    brand: str
    base_url: str
    entity_type: str
    start_urls: list[str]
    include_patterns: list[str]
    product_url_patterns: list[str]
    exclude_url_patterns: list[str]
    discovery_regexes: list[str]
    inline_products: bool
    max_depth: int
    max_products: int
    client: SimpleHttpClient

    def _match_include(self, url: str) -> bool:
        return any(pat in url for pat in self.include_patterns) if self.include_patterns else True

    def _match_product(self, url: str) -> bool:
        return any(re.search(pat, url) for pat in self.product_url_patterns)

    def _is_excluded(self, url: str) -> bool:
        return any(pat in url for pat in self.exclude_url_patterns)

    def _discover_with_regexes(self, current_url: str, text: str) -> set[str]:
        discovered: set[str] = set()
        for pattern in self.discovery_regexes:
            for match in re.finditer(pattern, text):
                raw = match.group(0)
                url = _normalize_url(current_url, raw)
                if url and not self._is_excluded(url):
                    discovered.add(url)
        return discovered

    def _extract_inline_oyama_products(self, start_url: str, text: str) -> list[dict[str, Any]]:
        heading_map = {
            "https://www.oyama.com/foldingbike": "folding",
            "https://www.oyama.com/roadbike": "road",
            "https://www.oyama.com/mountainbike": "mountain",
            "https://www.oyama.com/ebike": "ebike",
        }
        category = heading_map.get(start_url, "bike")
        blocks = re.split(r"\n\s*\n", text)
        products: list[dict[str, Any]] = []
        current_name = None
        current_specs: list[dict[str, str]] = []

        def flush() -> None:
            nonlocal current_name, current_specs
            if not current_name:
                return
            components = _extract_components(current_specs)
            source_id = f"{start_url}#{current_name.lower()}"
            products.append(
                {
                    "entity": "official_bike",
                    "source": f"official_{self.brand}",
                    "source_id": source_id,
                    "brand": self.brand,
                    "bike_name": current_name,
                    "bike_url": start_url,
                    "price_text": None,
                    "description": f"{self.brand.title()} {category} product page inline specification block",
                    "front_view_url": None,
                    "side_view_url": None,
                    "rear_view_url": None,
                    "all_images": [],
                    "components": components[:120],
                    "specs": current_specs[:200],
                    "payload": {"inline_category": category},
                }
            )
            current_name = None
            current_specs = []

        for block in blocks:
            lines = [_clean_text(line) for line in block.splitlines() if _clean_text(line)]
            if not lines:
                continue
            first = lines[0]
            if (
                re.fullmatch(r"[A-Z0-9][A-Z0-9\-\s]{1,}", first)
                or re.fullmatch(r"[A-Z][A-Z0-9\-]+", first)
            ) and "：" not in first and ":" not in first and "CONNECT" not in first.upper():
                flush()
                current_name = first
                current_specs = []
                continue
            if current_name:
                current_specs.extend(_extract_specs_from_markdownish_lines("\n".join(lines)))
        flush()
        if not products:
            raw_lines = [_clean_text(line) for line in text.splitlines() if _clean_text(line)]
            for idx, line in enumerate(raw_lines):
                if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-\s]{1,}", line):
                    continue
                if idx + 1 >= len(raw_lines):
                    continue
                window = "\n".join(raw_lines[idx + 1 : idx + 12])
                specs = _extract_specs_from_markdownish_lines(window)
                if len(specs) < 2:
                    continue
                products.append(
                    {
                        "entity": "official_bike",
                        "source": f"official_{self.brand}",
                        "source_id": f"{start_url}#{line.lower()}",
                        "brand": self.brand,
                        "bike_name": line,
                        "bike_url": start_url,
                        "price_text": None,
                        "description": f"{self.brand.title()} {category} product page inline specification block",
                        "front_view_url": None,
                        "side_view_url": None,
                        "rear_view_url": None,
                        "all_images": [],
                        "components": _extract_components(specs)[:120],
                        "specs": specs[:200],
                        "payload": {"inline_category": category, "fallback_parser": True},
                    }
                )
        return products[: self.max_products]

    def discover_product_urls(self) -> list[str]:
        if self.inline_products:
            return self.start_urls[:]
        queue = [(url, 0) for url in self.start_urls]
        visited: set[str] = set()
        products: set[str] = set()

        while queue and len(products) < self.max_products:
            current_url, depth = queue.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)
            if self._is_excluded(current_url):
                continue
            try:
                text = self.client.get_text(current_url)
            except Exception:
                continue
            soup = BeautifulSoup(text, "lxml")
            for regex_url in self._discover_with_regexes(current_url, text):
                if self._match_product(regex_url):
                    products.add(regex_url)
            if self.brand == "giant":
                for heading in soup.find_all(["h2", "h3"]):
                    anchor = heading.find("a", href=True)
                    if not anchor:
                        continue
                    next_url = _normalize_url(current_url, anchor["href"])
                    if next_url and self._match_product(next_url):
                        products.add(next_url)
            if self.brand == "shimano":
                for anchor in soup.find_all("a", href=True):
                    next_url = _normalize_url(current_url, anchor["href"])
                    if next_url and "/products/components/pdp." in next_url:
                        products.add(next_url)
            for link in soup.find_all("a", href=True):
                next_url = _normalize_url(current_url, link["href"])
                if not next_url:
                    continue
                if self._is_excluded(next_url):
                    continue
                if urlparse(next_url).netloc != urlparse(self.base_url).netloc:
                    continue
                if self._match_product(next_url):
                    products.add(next_url)
                if depth < self.max_depth and self._match_include(next_url) and next_url not in visited:
                    queue.append((next_url, depth + 1))
                if len(products) >= self.max_products:
                    break
        return sorted(products)[: self.max_products]

    def crawl_product(self, product_url: str) -> dict[str, Any] | None:
        if self.inline_products:
            try:
                text = self.client.get_text(product_url)
            except Exception:
                return None
            inline_rows = self._extract_inline_oyama_products(product_url, text)
            return inline_rows[0] if inline_rows else None
        try:
            html = self.client.get_text(product_url)
        except Exception:
            return None
        soup = BeautifulSoup(html, "lxml")

        title = None
        h1 = soup.find("h1")
        if h1:
            title = _clean_text(h1.get_text(" ", strip=True))
        if not title and soup.title:
            title = _clean_text(soup.title.get_text(" ", strip=True))

        json_ld_products = _extract_json_ld_products(soup)
        image_urls: list[str] = []
        price_text = None
        description = None

        for product in json_ld_products:
            image = product.get("image")
            if isinstance(image, str):
                image_urls.append(image)
            elif isinstance(image, list):
                image_urls.extend(str(v) for v in image if isinstance(v, str))
            title = title or product.get("name")
            description = description or product.get("description")
            offers = product.get("offers")
            if isinstance(offers, dict):
                p = offers.get("price")
                cur = offers.get("priceCurrency")
                if p:
                    price_text = f"{cur or ''} {p}".strip()

        for img in soup.find_all("img", src=True):
            src = _normalize_url(product_url, img.get("src", ""))
            if src and src not in image_urls and _looks_like_product_image(src):
                image_urls.append(src)
            if len(image_urls) >= 15:
                break

        body_text = _clean_text(soup.get_text(" ", strip=True))[:3000]
        price_text = price_text or _extract_price_text(body_text)
        specs = _extract_specs_from_tables(soup) + _extract_specs_from_text(soup)
        if self.brand == "giant":
            specs.extend(_extract_specs_from_markdownish_lines(soup.get_text("\n", strip=True)))
        if self.brand == "shimano":
            specs.extend(_extract_specs_from_markdownish_lines(soup.get_text("\n", strip=True)))
        unique_specs = []
        seen = set()
        for spec in specs:
            key = (spec["name"].lower(), spec["value"].lower())
            if key in seen:
                continue
            seen.add(key)
            unique_specs.append(spec)

        components = _extract_components(unique_specs)
        views = _classify_images(image_urls)

        entity = "official_component" if self.entity_type == "component" else "official_bike"
        record = {
            "entity": entity,
            "source": f"official_{self.brand}",
            "source_id": product_url,
            "brand": self.brand,
            "bike_name": title or "",
            "bike_url": product_url,
            "price_text": price_text,
            "description": description or body_text[:800],
            "front_view_url": views["front_view_url"],
            "side_view_url": views["side_view_url"],
            "rear_view_url": views["rear_view_url"],
            "all_images": image_urls[:20],
            "components": components[:120],
            "specs": unique_specs[:200],
            "payload": {
                "json_ld_products_count": len(json_ld_products),
                "raw_text_preview": body_text[:1000],
            },
        }
        if entity == "official_component":
            record["component_name"] = title or ""
            record["component_url"] = product_url
            record["component_category"] = unique_specs[0]["value"] if unique_specs else None
        return record

    def crawl(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if self.inline_products:
            for url in self.start_urls:
                try:
                    text = self.client.get_text(url)
                except Exception:
                    continue
                rows.extend(self._extract_inline_oyama_products(url, text))
            return rows[: self.max_products]

        for url in self.discover_product_urls():
            item = self.crawl_product(url)
            if not item:
                continue
            if item.get("entity") == "official_component" and item.get("component_name"):
                rows.append(item)
            elif item.get("bike_name"):
                rows.append(item)
        return rows
