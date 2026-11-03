import logging
import os
import re
import time
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class IMDbSyncScraper:
    def __init__(self, headless: bool = True, timeout: int = 20):
        self.timeout = timeout
        self.options = Options()
        if headless:
            self.options.add_argument("--headless=new")
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_argument("--disable-features=Translate,OptimizationHints")
        self.options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        chrome_bin = os.getenv("CHROME_BIN")
        chromedriver_path = os.getenv("CHROMEDRIVER_PATH")

        if chrome_bin:
            self.options.binary_location = chrome_bin

        try:
            if chromedriver_path and os.path.exists(chromedriver_path):
                service = Service(executable_path=chromedriver_path)
            else:
                service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=self.options)
            self.driver.set_page_load_timeout(self.timeout + 10)
        except Exception as exc:
            logger.exception("Failed to initialize Chromium for IMDb scraping")
            raise RuntimeError(f"Unable to start Chrome/Chromium: {exc}") from exc

    def _scroll_to_bottom(self):
        if not self.driver:
            return

        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
        except Exception:
            return

        for _ in range(10):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)
            try:
                new_height = self.driver.execute_script("return document.body.scrollHeight")
            except Exception:
                break
            if new_height == last_height:
                break
            last_height = new_height

    @staticmethod
    def _clean_title(title: str) -> str:
        if not title:
            return ""
        title = title.strip()
        title = re.sub(r"^\d+[\s\.]\s*", "", title)
        return title

    @staticmethod
    def _extract_imdb_id(href: str) -> str:
        if not href:
            return ""
        match = re.search(r"/title/(tt\d+)", href)
        return match.group(1) if match else ""

    def fetch_list_items(self, url: str) -> List[Dict[str, Any]]:
        if not url or not url.startswith(("http://", "https://")):
            raise ValueError("A valid IMDb URL is required.")

        logger.info("Fetching URL: %s", url)
        self.driver.get(url)

        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: d.execute_script("return document.body is not null")
            )
        except Exception as exc:
            logger.warning("Page did not load fully before timeout: %s", exc)

        self._scroll_to_bottom()

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        items: List[Dict[str, Any]] = []

        list_elements = soup.select(
            "li.ipc-metadata-list-summary-item, "
            "div.ipc-metadata-list-summary-item, "
            "div.lister-item, "
            "li.lister-item"
        )

        if not list_elements:
            anchors = soup.select("a[href*='/title/']")
            for anchor in anchors:
                href = anchor.get("href", "")
                imdb_id = self._extract_imdb_id(href)
                if not imdb_id:
                    continue
                title = self._clean_title(anchor.get_text(" ", strip=True))
                if not title:
                    continue
                items.append({
                    "position": len(items) + 1,
                    "imdb_id": imdb_id,
                    "title": title,
                    "year": "",
                    "rating": "N/A",
                    "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                })
            logger.info("Successfully scraped %s items using fallback anchor parsing.", len(items))
            return items

        for idx, el in enumerate(list_elements, start=1):
            title_el = (
                el.select_one("a[href*='/title/']")
                or el.select_one("a.ipc-title-link-wrapper")
                or el.select_one("h3 a[href*='/title/']")
            )
            if not title_el:
                continue

            href = title_el.get("href", "")
            imdb_id = self._extract_imdb_id(href)
            if not imdb_id:
                continue

            title_text = self._clean_title(title_el.get_text(" ", strip=True))
            if not title_text:
                continue

            year_el = el.select_one("span.sc-b15896e3-6, span.lister-item-year, span.ipc-title-meta")
            year = year_el.get_text(" ", strip=True) if year_el else ""

            rating_el = (
                el.select_one("span.ipc-rating-star--rating")
                or el.select_one("span.value")
                or el.select_one("span[aria-label*='rating']")
            )
            rating = rating_el.get_text(" ", strip=True) if rating_el else "N/A"

            items.append({
                "position": idx,
                "imdb_id": imdb_id,
                "title": title_text,
                "year": year,
                "rating": rating,
                "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
            })

        logger.info("Successfully scraped %s items.", len(items))
        return items

    def close(self):
        if getattr(self, "driver", None):
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
