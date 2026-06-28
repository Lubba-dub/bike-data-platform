from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from bike_data_platform.collectors.official_sites import (
    _classify_images,
    _clean_text,
    _extract_components,
    _extract_json_ld_products,
    _extract_price_text,
    _extract_specs_from_markdownish_lines,
    _extract_specs_from_tables,
    _extract_specs_from_text,
    _looks_like_product_image,
)

NON_BIKE_PRODUCT_KEYWORDS = (
    "jersey",
    "bibshort",
    "sock",
    "helmet",
    "shoe",
    "cockpit",
    "extension",
    "glove",
    "jacket",
    "bottle",
    "bag",
    "pump",
    "tool",
)

CANNONDALE_BIKE_URL_RE = re.compile(
    r"/en(?:-us)?/bikes/(road|mountain)/(race|endurance|gravel|cyclocross|trail-bikes|cross-country-bikes|downhill-bikes)/([^/]+)(?:/([^/]+))?(?:/\d{4})?$|/en(?:-us)?/bikes/electric/e-mountain/([^/]+)(?:/([^/]+))?(?:/\d{4})?$"
)

MTB_PRODUCT_SIGNALS = {
    "trek": (
        "mountain",
        "slash",
        "fuel exe",
        "top fuel",
        "supercaliber",
        "roscoe",
        "marlin",
        "remedy",
        "session",
    ),
    "canyon": (
        "mountain",
        "spectral",
        "neuron",
        "lux",
        "stoic",
        "sender",
        "torque",
        "strive",
        "grand canyon",
    ),
    "cannondale": (
        "mountain",
        "habit",
        "scalpel",
        "jekyll",
        "moterra",
        "trail",
        "f-si",
    ),
}

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    PlaywrightTimeoutError = RuntimeError
    sync_playwright = None


def _extract_links(html: str, base_url: str, patterns: list[str]) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    seen: set[str] = set()
    regexes = [re.compile(pattern) for pattern in patterns if pattern]
    if not regexes:
        return urls
    for link in soup.find_all("a", href=True):
        href = urljoin(base_url, link["href"])
        if href in seen:
            continue
        if any(regex.search(href) for regex in regexes):
            seen.add(href)
            urls.append(href)
    return urls


def _extract_regex_links(text: str, base_url: str, patterns: list[str]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        if not pattern:
            continue
        for match in re.finditer(pattern, text):
            raw = re.split(r'["\'<>\s]', match.group(0), maxsplit=1)[0].rstrip("),.;")
            if not raw:
                continue
            href = urljoin(base_url, raw)
            if href in seen:
                continue
            seen.add(href)
            urls.append(href)
    return urls


def _clean_product_title(value: str | None, brand: str) -> str:
    title = _clean_text(value or "")
    suffixes = [
        f" - {brand.title()} Bikes",
        f" - {brand.title()} Bicycle",
        f" - {brand.title()} Bicycle Store",
        f" - {brand.title()}",
        f" | {brand.title()} Bicycle",
        f" | {brand.title()}",
    ]
    for suffix in suffixes:
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
    return title


def _is_plausible_spec(name: str, value: str) -> bool:
    key = _clean_text(name)
    val = _clean_text(value)
    if not key or not val:
        return False
    if len(key) > 80 or len(val) > 240:
        return False
    lower = val.lower()
    noisy_tokens = (
        "shop all",
        "learn more",
        "need help",
        "previous slide",
        "next slide",
        "filter by",
        "resultresults",
    )
    if any(token in lower for token in noisy_tokens):
        return False
    return True


def _path_segments(url: str) -> list[str]:
    return [segment for segment in urlparse(url).path.split("/") if segment]


def _prepare_discovery_page(page, brand: str) -> str:
    _dismiss_cookie_banner(page)
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=5000)
    if brand in {"trek", "cannondale"}:
        rounds = 4 if brand == "trek" else 3
        delay = 1200 if brand == "trek" else 1800
        for _ in range(rounds):
            with contextlib.suppress(Exception):
                page.mouse.wheel(0, 1800)
            with contextlib.suppress(Exception):
                page.wait_for_timeout(delay)
    else:
        with contextlib.suppress(Exception):
            page.wait_for_timeout(1200)
    return page.content()


def _is_valid_bike_url(brand: str, url: str) -> bool:
    lower = url.lower()
    if brand == "canyon":
        if any(token in lower for token in ("/gear/", "/apparel/", "/outlet/", "/collections/")):
            return False
        return any(
            token in lower
            for token in ("/road-bikes/", "/gravel-bikes/", "/mountain-bikes/", "/hybrid-bikes/", "/electric-bikes/")
        )
    if brand == "cannondale":
        match = CANNONDALE_BIKE_URL_RE.search(lower)
        return bool(match and any(match.group(i) for i in (3, 5) if match.lastindex and i <= match.lastindex))
    if brand == "trek":
        return "/us/en_us/bikes/" in lower and "/p/" in lower
    return True


def _is_valid_bike_record(
    brand: str,
    product_url: str,
    title: str | None,
    description: str | None,
    specs: list[dict[str, str]],
    components: list[dict[str, str]],
) -> bool:
    lower_title = (title or "").lower()
    lower_desc = (description or "").lower()
    combined_text = " ".join(part for part in (lower_title, lower_desc, product_url.lower()) if part)
    if not _is_valid_bike_url(brand, product_url):
        return False
    if brand == "canyon":
        if any(token in lower_title for token in NON_BIKE_PRODUCT_KEYWORDS):
            return False
        if any(token in lower_desc for token in NON_BIKE_PRODUCT_KEYWORDS):
            return False
    if brand == "cannondale":
        if "resultresults" in lower_desc:
            return False
        min_components = 2 if any(token in combined_text for token in MTB_PRODUCT_SIGNALS["cannondale"]) else 3
        min_specs = 8 if any(token in combined_text for token in MTB_PRODUCT_SIGNALS["cannondale"]) else 12
        if len(components) < min_components and len(specs) < min_specs:
            return False
    if brand == "trek":
        if lower_title.startswith("shop "):
            return False
        if "bike finder" in lower_title or "buyer" in lower_title:
            return False
        if "frameset" in lower_title and len(components) < 2:
            return False
    return True


def _dismiss_cookie_banner(page) -> None:
    for selector in [
        "button:has-text('I AGREE')",
        "button:has-text('I Agree')",
        "button:has-text('Accept')",
        "button:has-text('AGREE')",
    ]:
        with contextlib.suppress(Exception):
            locator = page.locator(selector).first
            if locator.is_visible(timeout=1000):
                locator.click(timeout=1000)
                return


def _extract_product_record(brand: str, entity_type: str, product_url: str, html: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "lxml")
    title = None
    meta_title = None
    for prop in ["og:title", "twitter:title"]:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            meta_title = _clean_text(tag["content"])
            break
    meta_description = None
    for key in ["description", "og:description", "twitter:description"]:
        tag = soup.find("meta", attrs={"name": key}) or soup.find("meta", attrs={"property": key})
        if tag and tag.get("content"):
            meta_description = _clean_text(tag["content"])
            break
    h1 = soup.find("h1")
    if h1:
        title = _clean_text(h1.get_text(" ", strip=True))
    title = title or meta_title
    if not title and soup.title:
        title = _clean_text(soup.title.get_text(" ", strip=True))
    title = _clean_product_title(title, brand)

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
            price = offers.get("price")
            currency = offers.get("priceCurrency")
            if price:
                price_text = f"{currency or ''} {price}".strip()

    for img in soup.find_all("img", src=True):
        src = urljoin(product_url, img.get("src", ""))
        if src not in image_urls and _looks_like_product_image(src):
            image_urls.append(src)
        if len(image_urls) >= 20:
            break

    page_text = soup.get_text("\n", strip=True)
    specs = (
        _extract_specs_from_tables(soup)
        + _extract_specs_from_text(soup)
        + _extract_specs_from_markdownish_lines(page_text)
    )
    unique_specs: list[dict[str, str]] = []
    seen_specs: set[tuple[str, str]] = set()
    for spec in specs:
        clean_name = _clean_text(spec["name"])
        clean_value = _clean_text(spec["value"])
        if not _is_plausible_spec(clean_name, clean_value):
            continue
        key = (clean_name.lower(), clean_value.lower())
        if key in seen_specs:
            continue
        seen_specs.add(key)
        unique_specs.append({"name": clean_name, "value": clean_value})

    components = _extract_components(unique_specs)
    views = _classify_images(image_urls)
    if entity_type != "component" and not _is_valid_bike_record(
        brand,
        product_url,
        title,
        description or meta_description or page_text[:500],
        unique_specs,
        components,
    ):
        return None
    record = {
        "source": f"official_{brand}",
        "source_id": product_url,
        "brand": brand,
        "price_text": price_text or _extract_price_text(page_text),
        "description": description or meta_description or _clean_text(page_text)[:1000],
        "front_view_url": views["front_view_url"],
        "side_view_url": views["side_view_url"],
        "rear_view_url": views["rear_view_url"],
        "all_images": image_urls[:20],
        "components": components[:120],
        "specs": unique_specs[:250],
        "payload": {
            "collector_mode": "browser_playwright",
            "json_ld_products_count": len(json_ld_products),
        },
    }
    if entity_type == "component":
        record["entity"] = "official_component"
        if title == "Product Detail Page" and meta_title:
            title = meta_title
        record["component_name"] = title or ""
        record["component_url"] = product_url
        record["component_category"] = None
    else:
        record["entity"] = "official_bike"
        record["bike_name"] = title or ""
        record["bike_url"] = product_url
    return record


def _discover_family_links(html: str, base_url: str, brand: str) -> list[str]:
    if brand != "trek":
        return []
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    seen: set[str] = set()
    family_patterns = [re.compile(r"/us/en_US/bikes/.+/f/F[A-Z0-9\-]+/?$"), re.compile(r"/us/en_US/bikes/.+/c/B\d+/?$")]
    for link in soup.find_all("a", href=True):
        href = urljoin(base_url, link["href"])
        if href in seen:
            continue
        if any(pattern.search(href) for pattern in family_patterns):
            seen.add(href)
            urls.append(href)
    return urls


@dataclass
class BrowserBrandCrawler:
    brand: str
    base_url: str
    entity_type: str
    start_urls: list[str]
    include_patterns: list[str]
    product_url_patterns: list[str]
    discovery_regexes: list[str]
    max_discovery_depth: int = 1
    max_products: int = 20
    headless: bool = False

    def _launch(self):
        if sync_playwright is None:
            raise RuntimeError("Playwright is not installed. Run `pip install playwright` first.")
        return sync_playwright().start()

    def _match_include(self, url: str) -> bool:
        return any(pattern in url for pattern in self.include_patterns) if self.include_patterns else True

    def _same_domain(self, url: str) -> bool:
        return urlparse(url).netloc == urlparse(self.base_url).netloc

    def _discover_product_urls(self, page, start_url: str) -> list[str]:
        queue: list[tuple[str, int]] = [(start_url, 0)]
        visited: set[str] = set()
        discovered: list[str] = []
        seen_products: set[str] = set()
        product_patterns = self.product_url_patterns or [r"/bikes-[a-z0-9\-]+"]
        regex_patterns = self.discovery_regexes or product_patterns

        while queue and len(discovered) < self.max_products:
            current_url, depth = queue.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            page.goto(current_url, wait_until="domcontentloaded", timeout=45000)
            html = _prepare_discovery_page(page, self.brand)

            for url in _extract_links(html, current_url, product_patterns) + _extract_regex_links(html, current_url, regex_patterns):
                if not self._same_domain(url):
                    continue
                if not _is_valid_bike_url(self.brand, url) and "/f/" not in url.lower() and "/c/" not in url.lower():
                    continue
                if url in seen_products:
                    continue
                seen_products.add(url)
                discovered.append(url)
                if len(discovered) >= self.max_products:
                    break

            if depth >= self.max_discovery_depth:
                continue
            soup = BeautifulSoup(html, "lxml")
            extra_queue_urls = _discover_family_links(html, current_url, self.brand)
            for next_url in extra_queue_urls:
                if self._same_domain(next_url) and next_url not in visited and self._match_include(next_url):
                    queue.append((next_url, depth + 1))
            for link in soup.find_all("a", href=True):
                next_url = urljoin(current_url, link["href"])
                if not self._same_domain(next_url):
                    continue
                if next_url in visited:
                    continue
                if not self._match_include(next_url):
                    continue
                queue.append((next_url, depth + 1))

        return discovered[: self.max_products]

    def _discover_shimano_product_urls(self, page, url: str) -> list[str]:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        _dismiss_cookie_banner(page)
        with contextlib.suppress(Exception):
            page.wait_for_selector("a.bike__link", timeout=5000)
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=5000)
        html = page.content()
        patterns = [r"/products/components/pdp\.P-[A-Za-z0-9\-]+\.html", r"/products/series/[A-Za-z0-9\-]+\.html"]
        urls = _extract_links(html, url, patterns)
        if urls:
            return urls
        # Fallback: wait briefly and retry once when the page performs a follow-up navigation.
        with contextlib.suppress(Exception):
            page.wait_for_timeout(1500)
        html = page.content()
        return _extract_links(html, url, patterns)

    def crawl(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        rows: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        playwright = self._launch()
        browser = playwright.chromium.launch(headless=self.headless)
        context = browser.new_context()
        page = context.new_page()

        try:
            discovered: list[str] = []
            if self.brand == "shimano":
                for start_url in self.start_urls:
                    try:
                        discovered.extend(self._discover_shimano_product_urls(page, start_url))
                    except Exception as exc:  # pragma: no cover - network dependent
                        errors.append({"brand": self.brand, "url": start_url, "error": str(exc)})
                discovered = discovered[: self.max_products]
            else:
                for start_url in self.start_urls:
                    try:
                        discovered.extend(self._discover_product_urls(page, start_url))
                    except Exception as exc:  # pragma: no cover - network dependent
                        errors.append({"brand": self.brand, "url": start_url, "error": str(exc)})
                seen: set[str] = set()
                discovered = [url for url in discovered if not (url in seen or seen.add(url))][: self.max_products]

            for product_url in discovered:
                try:
                    page.goto(product_url, wait_until="domcontentloaded", timeout=45000)
                    _dismiss_cookie_banner(page)
                    record = _extract_product_record(self.brand, self.entity_type, product_url, page.content())
                    if not record:
                        continue
                    if record.get("entity") == "official_bike" and record.get("bike_name"):
                        rows.append(record)
                    elif record.get("entity") == "official_component" and record.get("component_name"):
                        rows.append(record)
                except PlaywrightTimeoutError as exc:  # pragma: no cover - network dependent
                    errors.append({"brand": self.brand, "url": product_url, "error": f"timeout: {exc}"})
                except Exception as exc:  # pragma: no cover - network dependent
                    errors.append({"brand": self.brand, "url": product_url, "error": str(exc)})
        finally:
            context.close()
            browser.close()
            playwright.stop()

        return rows, errors
