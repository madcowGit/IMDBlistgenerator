import json
import logging
import os
import re
import time
from typing import Any, Dict, List

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
    def __init__(self, headless: bool = True, timeout: int = 20, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.driver = None
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-features=Translate,OptimizationHints")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        chrome_bin = os.getenv("CHROME_BIN")
        driver_path = os.getenv("CHROMEDRIVER_PATH")
        if chrome_bin:
            options.binary_location = chrome_bin

        try:
            service = Service(executable_path=driver_path) if driver_path and os.path.exists(driver_path) else Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(self.timeout + 10)
        except Exception as exc:
            logger.exception("Failed to initialize Chromium")
            raise RuntimeError(f"Unable to start Chrome/Chromium: {exc}") from exc

    def _scroll_to_bottom(self):
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
        except WebDriverException:
            return
        for _ in range(10):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)
            try:
                new_height = self.driver.execute_script("return document.body.scrollHeight")
            except WebDriverException:
                break
            if new_height == last_height:
                break
            last_height = new_height

    @staticmethod
    def _clean_title(title: str) -> str:
        return re.sub(r"^\d+[\s.]\s*", "", title.strip()) if title else ""

    @staticmethod
    def _extract_imdb_id(href: str) -> str:
        match = re.search(r"/title/(tt\d+)", href or "")
        return match.group(1) if match else ""

    @classmethod
    def _extract_json_ld_items(cls, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract movie entries from IMDb's structured-data scripts."""
        items: List[Dict[str, Any]] = []
        seen_ids = set()

        def visit(value):
            if isinstance(value, dict):
                entry = value.get("item", value)
                if isinstance(entry, dict):
                    href = entry.get("url") or entry.get("@id") or value.get("url") or value.get("@id") or ""
                    title = entry.get("name") or value.get("name") or ""
                else:
                    href = entry or value.get("url") or value.get("@id") or ""
                    title = value.get("name") or ""
                imdb_id = cls._extract_imdb_id(str(href))
                title = cls._clean_title(str(title))
                if imdb_id and title and imdb_id not in seen_ids:
                    seen_ids.add(imdb_id)
                    items.append({
                        "position": len(items) + 1,
                        "imdb_id": imdb_id,
                        "title": title,
                        "year": "",
                        "rating": "N/A",
                        "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                    })
                for nested_value in value.values():
                    visit(nested_value)
            elif isinstance(value, list):
                for nested_value in value:
                    visit(nested_value)

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                visit(json.loads(script.string or script.get_text()))
            except (json.JSONDecodeError, TypeError):
                continue
        return items

    def _load_page_with_retry(self, url: str):
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, self.timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")
                WebDriverWait(self.driver, self.timeout).until(lambda d: d.execute_script("return document.body !== null"))
                return
            except WebDriverException as exc:
                last_error = exc
                logger.warning("Page load attempt %s/%s failed: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Failed to load IMDb page after {self.max_retries} attempts: {last_error}")

    def fetch_list_items(self, url: str) -> List[Dict[str, Any]]:
        if not url or not url.startswith(("http://", "https://")):
            raise ValueError("A valid IMDb URL is required.")
        logger.info("Fetching URL: %s", url)
        try:
            self._load_page_with_retry(url)
        except RuntimeError as exc:
            logger.error("Could not fetch IMDb page: %s", exc)
            return []

        # IMDb hydrates list content after the initial document load.
        try:
            WebDriverWait(self.driver, min(self.timeout, 8)).until(
                lambda driver: driver.find_elements(By.CSS_SELECTOR, "a[href*='/title/']")
            )
        except TimeoutException:
            logger.debug("No IMDb title links appeared before the content wait expired")

        self._scroll_to_bottom()
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        page_title = self.driver.title or ""
        body_text = soup.body.get_text(" ", strip=True) if soup.body else ""
        verification_text = f"{page_title} {body_text}".casefold()
        if (
            "human verification" in page_title.casefold()
            or "confirm you are human" in verification_text
            or "security check before continuing" in verification_text
        ):
            logger.warning(
                "IMDb served a human-verification page (page_title=%r, current_url=%r)",
                page_title,
                self.driver.current_url,
            )
            raise IMDbVerificationRequired(
                "IMDb presented a human-verification page. The list could not be scraped."
            )

        items: List[Dict[str, Any]] = []
        elements = soup.select("li.ipc-metadata-list-summary-item, div.ipc-metadata-list-summary-item, div.lister-item, li.lister-item")

        if not elements:
            items = self._extract_json_ld_items(soup)
            if not items:
                seen_ids = set()
                for anchor in soup.select("a[href*='/title/']"):
                    imdb_id = self._extract_imdb_id(anchor.get("href", ""))
                    title = self._clean_title(
                        anchor.get_text(" ", strip=True)
                        or anchor.get("aria-label", "")
                        or anchor.get("title", "")
                    )
                    if imdb_id and title and imdb_id not in seen_ids:
                        seen_ids.add(imdb_id)
                        items.append({"position": len(items) + 1, "imdb_id": imdb_id, "title": title, "year": "", "rating": "N/A", "imdb_url": f"https://www.imdb.com/title/{imdb_id}/"})
            if not items:
                logger.warning(
                    "IMDb page had no extractable titles (page_title=%r, current_url=%r, body_excerpt=%r)",
                    page_title,
                    self.driver.current_url,
                    body_text[:300],
                )
            logger.info("Extracted %s items using fallback parsing", len(items))
            return items

        for element in elements:
            title_el = element.select_one("a[href*='/title/']")
            if not title_el:
                continue
            imdb_id = self._extract_imdb_id(title_el.get("href", ""))
            title = self._clean_title(
                title_el.get_text(" ", strip=True)
                or title_el.get("aria-label", "")
                or title_el.get("title", "")
            )
            if not imdb_id or not title:
                continue
            year_el = element.select_one("span.sc-b15896e3-6, span.lister-item-year, span.ipc-title-meta")
            rating_el = element.select_one("span.ipc-rating-star--rating, span.value, span[aria-label*='rating']")
            items.append({
                "position": len(items) + 1,
                "imdb_id": imdb_id,
                "title": title,
                "year": year_el.get_text(" ", strip=True) if year_el else "",
                "rating": rating_el.get_text(" ", strip=True) if rating_el else "N/A",
                "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
            })
        logger.info("Successfully scraped %s items", len(items))
        return items

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                logger.debug("Error closing browser", exc_info=True)
            self.driver = None
