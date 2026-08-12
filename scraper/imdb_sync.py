import os
import time
import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

class IMDbSyncScraper:
    def __init__(self, headless: bool = True, timeout: int = 15):
        self.timeout = timeout
        self.options = Options()
        if headless:
            self.options.add_argument("--headless=new")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        chrome_bin = os.getenv("CHROME_BIN")
        chromedriver_path = os.getenv("CHROMEDRIVER_PATH")

        if chrome_bin:
            self.options.binary_location = chrome_bin

        if chromedriver_path and os.path.exists(chromedriver_path):
            service = Service(executable_path=chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())

        self.driver = webdriver.Chrome(service=service, options=self.options)

    def _scroll_to_bottom(self):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def fetch_list_items(self, url: str) -> List[Dict[str, Any]]:
        logger.info(f"Fetching URL: {url}")
        self.driver.get(url)
        
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
            )
        except Exception as e:
            logger.error(f"Timeout waiting for page content: {e}")
            return []

        self._scroll_to_bottom()

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        items = []

        list_elements = soup.select("li.ipc-metadata-list-summary-item, div.lister-item")

        for idx, el in enumerate(list_elements, start=1):
            title_el = el.select_one("a.ipc-title-link-wrapper, h3.lister-item-header a")
            if not title_el:
                continue

            href = title_el.get("href", "")
            imdb_id = ""
            if "/title/" in href:
                imdb_id = href.split("/title/")[1].split("/")[0]

            title_text = title_el.get_text(strip=True)
            if title_text and title_text[0].isdigit() and "." in title_text:
                title_text = title_text.split(".", 1)[1].strip()

            year_el = el.select_one("span.sc-b15896e3-6, span.lister-item-year")
            year = year_el.get_text(strip=True) if year_el else ""

            rating_el = el.select_one("span.ipc-rating-star--rating, span.value")
            rating = rating_el.get_text(strip=True) if rating_el else "N/A"

            items.append({
                "position": idx,
                "imdb_id": imdb_id,
                "title": title_text,
                "year": year,
                "rating": rating,
                "imdb_url": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else ""
            })

        logger.info(f"Successfully scraped {len(items)} items.")
        return items

    def close(self):
        if self.driver:
            self.driver.quit()
