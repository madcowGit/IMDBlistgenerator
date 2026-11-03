import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class IMDbVerificationRequired(RuntimeError):
    """Raised when IMDb serves a human-verification page instead of list content."""


class IMDbSyncScraper:
    """Fetch public IMDb list pages politely, stopping if IMDb requests verification."""

    def __init__(self, headless: bool = True, timeout: int = 20, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.max_pages = max(1, int(os.getenv("IMDB_MAX_PAGES", "100")))
        self.request_delay = max(0.5, float(os.getenv("IMDB_REQUEST_DELAY", "1.0")))
        self.driver = None

        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=en-US")

        chrome_bin = os.getenv("CHROME_BIN")
        driver_path = os.getenv("CHROMEDRIVER_PATH")
        if chrome_bin:
            options.binary_location = chrome_bin

        try:
            service = (
                Service(executable_path=driver_path)
                if driver_path and os.path.exists(driver_path)
                else Service(ChromeDriverManager().install())
            )
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(self.timeout + 10)
        except Exception as exc:
            logger.exception("Failed to initialize Chromium")
            raise RuntimeError(f"Unable to start Chrome/Chromium: {exc}") from exc

    def _scroll_to_load_content(self):
        """Scroll a bounded amount to allow lazy-loaded list rows to appear."""
        unchanged = 0
        previous_height = 0
        for _ in range(8):
            try:
                height = self.driver.execute_script("return document.body.scrollHeight")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            except WebDriverException:
                return
            if height == previous_height:
                unchanged += 1
                if unchanged >= 2:
                    break
            else:
                unchanged = 0
            previous_height = height
            time.sleep(0.5)

    @staticmethod
    def _clean_title(title: str) -> str:
        return re.sub(r"^\d+[\s.]+", "", title.strip()) if title else ""

    @staticmethod
    def _extract_imdb_id(href: str) -> str:
        match = re.search(r"/title/(tt\d+)", href or "")
        return match.group(1) if match else ""

    @classmethod
    def _extract_json_ld_items(cls, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract only entries explicitly represented as an ItemList in JSON-LD."""
        extracted: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        def find_item_lists(value):
            if isinstance(value, dict):
                item_type = value.get("@type", [])
                if isinstance(item_type, str):
                    item_type = [item_type]
                if "ItemList" in item_type:
                    for entry in value.get("itemListElement", []):
                        if not isinstance(entry, dict):
                            continue
                        item = entry.get("item", entry)
                        if not isinstance(item, dict):
                            continue
                        href = item.get("url") or item.get("@id") or ""
                        imdb_id = cls._extract_imdb_id(str(href))
                        title = cls._clean_title(str(item.get("name") or ""))
                        if imdb_id and title and imdb_id not in seen:
                            seen.add(imdb_id)
                            extracted.append(cls._make_item(imdb_id, title, len(extracted) + 1))
                for nested in value.values():
                    find_item_lists(nested)
            elif isinstance(value, list):
                for nested in value:
                    find_item_lists(nested)

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                find_item_lists(json.loads(script.string or script.get_text()))
            except (json.JSONDecodeError, TypeError):
                continue
        return extracted

    @staticmethod
    def _make_item(imdb_id: str, title: str, position: int, year: str = "", rating: str = "N/A") -> Dict[str, Any]:
        return {
            "position": position,
            "imdb_id": imdb_id,
            "title": title,
            "year": year,
            "rating": rating,
            "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
        }

    @classmethod
    def _parse_page(cls, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        selectors = (
            "li.ipc-metadata-list-summary-item, div.ipc-metadata-list-summary-item, "
            "div.lister-item, li.lister-item"
        )
        for element in soup.select(selectors):
            title_el = element.select_one("a[href*='/title/']")
            if not title_el:
                continue
            imdb_id = cls._extract_imdb_id(title_el.get("href", ""))
            title = cls._clean_title(
                title_el.get_text(" ", strip=True)
                or title_el.get("aria-label", "")
                or title_el.get("title", "")
            )
            if not imdb_id or not title or imdb_id in seen:
                continue
            seen.add(imdb_id)
            year_el = element.select_one(
                "span.sc-b15896e3-6, span.lister-item-year, span.ipc-title-meta"
            )
            rating_el = element.select_one(
                "span.ipc-rating-star--rating, span.value, span[aria-label*='rating']"
            )
            items.append(cls._make_item(
                imdb_id,
                title,
                len(items) + 1,
                year_el.get_text(" ", strip=True) if year_el else "",
                rating_el.get_text(" ", strip=True) if rating_el else "N/A",
            ))

        if items:
            return items
        items = cls._extract_json_ld_items(soup)
        if items:
            return items

        # Last-resort parsing for IMDb markup changes: accept title links inside
        # list-like containers only, avoiding unrelated recommendations on page.
        for container in soup.select("main, [role='main'], .lister, .ipc-page-content-container"):
            for anchor in container.select("a[href*='/title/']"):
                imdb_id = cls._extract_imdb_id(anchor.get("href", ""))
                title = cls._clean_title(
                    anchor.get_text(" ", strip=True)
                    or anchor.get("aria-label", "")
                    or anchor.get("title", "")
                )
                if imdb_id and title and imdb_id not in seen:
                    seen.add(imdb_id)
                    items.append(cls._make_item(imdb_id, title, len(items) + 1))
        return items

    def _load_page_with_retry(self, url: str):
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, self.timeout).until(
                    lambda driver: driver.execute_script("return document.readyState") in ("interactive", "complete")
                )
                WebDriverWait(self.driver, self.timeout).until(
                    lambda driver: driver.execute_script("return document.body !== null")
                )
                return
            except WebDriverException as exc:
                last_error = exc
                logger.warning("Page load attempt %s/%s failed: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"Failed to load IMDb page after {self.max_retries} attempts: {last_error}")

    @staticmethod
    def _verification_detected(page_title: str, current_url: str, body_text: str) -> bool:
        text = f"{page_title} {current_url} {body_text[:3000]}".casefold()
        return any(marker in text for marker in (
            "human verification",
            "confirm you are human",
            "security check before continuing",
            "verify you are human",
            "captcha",
        ))

    @staticmethod
    def _next_page_url(soup: BeautifulSoup, current_url: str) -> Optional[str]:
        link = soup.select_one("a[rel~='next']")
        if not link:
            for anchor in soup.select("a[href]"):
                label = " ".join((anchor.get("aria-label", ""), anchor.get("title", ""), anchor.get_text(" ", strip=True))).casefold()
                if label.strip() in {"next", "next page"} or "next page" in label:
                    link = anchor
                    break
        if not link or not link.get("href"):
            return None
        next_url = urljoin(current_url, link["href"])
        parsed = urlparse(next_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"imdb.com", "www.imdb.com"}:
            return None
        return urlunparse(parsed._replace(fragment=""))

    def fetch_list_items(self, url: str) -> List[Dict[str, Any]]:
        parsed = urlparse(url or "")
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"imdb.com", "www.imdb.com"}:
            raise ValueError("A valid IMDb list URL is required.")

        current_url = url
        visited: Set[str] = set()
        all_items: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()

        for page_number in range(1, self.max_pages + 1):
            if current_url in visited:
                logger.info("Stopping IMDb pagination because a page URL repeated")
                break
            visited.add(current_url)
            logger.info("Fetching IMDb list page %s", page_number)
            if page_number > 1:
                time.sleep(self.request_delay)
            try:
                self._load_page_with_retry(current_url)
            except RuntimeError:
                if not all_items:
                    raise
                logger.warning("Could not load subsequent page; returning %s items collected", len(all_items))
                break

            try:
                WebDriverWait(self.driver, min(self.timeout, 8)).until(
                    lambda driver: driver.find_elements(By.CSS_SELECTOR, "a[href*='/title/']")
                )
            except TimeoutException:
                logger.debug("No IMDb title links appeared before the content wait expired")

            self._scroll_to_load_content()
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            page_title = self.driver.title or ""
            body_text = soup.body.get_text(" ", strip=True) if soup.body else ""
            if self._verification_detected(page_title, self.driver.current_url, body_text):
                logger.warning("IMDb requested human verification (title=%r, url=%r)", page_title, self.driver.current_url)
                raise IMDbVerificationRequired(
                    "IMDb presented a human-verification page. The list could not be scraped; no verification bypass is attempted."
                )

            page_items = self._parse_page(soup)
            for item in page_items:
                if item["imdb_id"] not in seen_ids:
                    seen_ids.add(item["imdb_id"])
                    item["position"] = len(all_items) + 1
                    all_items.append(item)

            next_url = self._next_page_url(soup, self.driver.current_url)
            if not next_url or next_url in visited:
                break
            current_url = next_url
        else:
            logger.warning("Reached configured IMDb page limit (%s)", self.max_pages)

        logger.info("Successfully scraped %s unique items across %s page(s)", len(all_items), len(visited))
        return all_items

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                logger.debug("Error closing browser", exc_info=True)
            self.driver = None
