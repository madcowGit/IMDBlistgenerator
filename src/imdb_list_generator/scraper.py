import json
import logging
import os
import re
import shutil
import ssl
import tempfile
import time
from contextlib import contextmanager
from typing import Any, NotRequired, TypedDict
from urllib.error import URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import certifi
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import Chrome
from selenium.webdriver.remote.webelement import WebElement
from seleniumbase import SB
from seleniumbase import undetected as uc
from seleniumbase.common.exceptions import NoSuchElementException

logger = logging.getLogger(__name__)

TVDB_API_URL = "https://api4.thetvdb.com/v4"
ITEM_SELECTOR = "li.ipc-metadata-list-summary-item"
TITLE_SELECTOR = "a.ipc-title-link-wrapper, a[href*='/title/tt']"
YEAR_SELECTOR = (
    "span.dli-title-metadata-item, "
    "li.cli-title-metadata-item, "
    "span.cli-title-metadata-item, "
    "li.ipc-inline-list__item"
)


class Movie(TypedDict):
    title: str
    imdb_id: str
    poster_url: str | None
    year: int | None
    rating: float | None
    tvdb_id: NotRequired[int | None]


class SystemChromiumBrowser:
    def __init__(self, driver: Chrome) -> None:
        self.driver = driver

    def uc_open_with_reconnect(self, url: str, reconnect_time: int) -> None:
        self.driver.get(url)

    def wait_for_element_present(self, selector: str, timeout: int) -> None:
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(self.driver, timeout).until(
            lambda driver: driver.find_elements("css selector", selector)
        )

    def find_elements(self, selector: str) -> list[WebElement]:
        return self.driver.find_elements("css selector", selector)

    def scroll_to_bottom(self) -> None:
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    @staticmethod
    def sleep(seconds: int) -> None:
        time.sleep(seconds)


@contextmanager
def _browser():
    if os.environ.get("IMDB_USE_SYSTEM_CHROMIUM") == "1":
        with tempfile.TemporaryDirectory(prefix="imdb-chromedriver-") as temp_dir:
            driver_path = os.path.join(temp_dir, "chromedriver")
            shutil.copy2(
                os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver"),
                driver_path,
            )
            os.chmod(driver_path, 0o755)
            options = uc.ChromeOptions()
            options.binary_location = os.environ.get(
                "CHROMIUM_BINARY", "/usr/bin/chromium"
            )
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = uc.Chrome(
                options=options,
                driver_executable_path=driver_path,
                browser_executable_path=options.binary_location,
                use_subprocess=True,
            )
            try:
                yield SystemChromiumBrowser(driver)
            finally:
                driver.quit()
    else:
        with SB(uc=True, headless=False) as sb:
            yield sb


def _validate_imdb_url(url: str) -> None:
    parsed_url = urlsplit(url)
    if parsed_url.scheme not in {"http", "https"} or parsed_url.hostname not in {
        "imdb.com",
        "www.imdb.com",
    }:
        raise ValueError("URL must be an IMDb list or watchlist URL")

    is_list = re.fullmatch(r"/list/ls\d+/?", parsed_url.path)
    is_watchlist = re.fullmatch(r"/user/[^/]+/watchlist/?", parsed_url.path)
    is_top_chart = re.fullmatch(r"/chart/top/?", parsed_url.path)
    if not (is_list or is_watchlist or is_top_chart):
        raise ValueError(
            "URL must point to an IMDb list, user watchlist, or Top 250 chart"
        )


def _url_for_page(url: str, page_number: int) -> str:
    parsed_url = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
        if key != "page"
    ]
    if page_number > 1:
        query.append(("page", str(page_number)))
    return urlunsplit(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            urlencode(query),
            parsed_url.fragment,
        )
    )


def _is_tv_series_element(element: WebElement) -> bool:
    return any(
        metadata.text.strip().casefold() in {"tv series", "tv mini series"}
        for metadata in element.find_elements("css selector", YEAR_SELECTOR)
    )


def _tvdb_request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=data, headers=headers, method=method)

    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=20, context=context) as response:
            result = json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "TVDB request failed; check the API key and connectivity."
        ) from exc

    if not isinstance(result, dict) or result.get("status") != "success":
        raise RuntimeError("TVDB returned an unsuccessful or invalid response.")
    return result


def _get_tvdb_token(api_key: str) -> str:
    payload = json.dumps({"apikey": api_key}).encode("utf-8")
    response = _tvdb_request(f"{TVDB_API_URL}/login", method="POST", data=payload)
    data = response.get("data")
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("TVDB login response did not contain an API token.")
    return token


def _lookup_tvdb_id(imdb_id: str, token: str) -> int | None:
    response = _tvdb_request(
        f"{TVDB_API_URL}/search/remoteid/{quote(imdb_id, safe='')}", token=token
    )
    results = response.get("data")
    if not isinstance(results, list):
        raise RuntimeError("TVDB lookup response did not contain a result list.")

    for result in results:
        if not isinstance(result, dict):
            continue
        series = result.get("series")
        series_result = series if isinstance(series, dict) else result
        if series is None and result.get("type") not in (None, "series"):
            continue
        tvdb_id = series_result.get("id", series_result.get("tvdb_id"))
        if isinstance(tvdb_id, int):
            return tvdb_id
        if isinstance(tvdb_id, str) and tvdb_id.isdigit():
            return int(tvdb_id)
    return None


def parse_movie_element(element: WebElement) -> Movie | None:
    """Parse an IMDb item into Steven Lu's JSON layout."""
    title_elements = element.find_elements("css selector", TITLE_SELECTOR)
    title = None
    imdb_id = None
    for title_el in title_elements:
        href = title_el.get_attribute("href") or ""
        match = re.search(r"tt\d+", href)
        raw_title = title_el.text.strip()
        if not raw_title:
            raw_title = title_el.get_attribute("textContent") or ""
        candidate_title = re.sub(r"^\d+\.\s*", "", raw_title).strip()
        if match and candidate_title:
            title = candidate_title
            imdb_id = match.group(0)
            break

    if not title or not imdb_id:
        return None

    image_elements = element.find_elements("css selector", "img.ipc-image")
    poster_url = None
    if image_elements:
        poster_url = image_elements[0].get_attribute("src") or image_elements[
            0
        ].get_attribute("data-src")

    year = None
    for metadata in element.find_elements("css selector", YEAR_SELECTOR):
        year_match = re.search(r"\b(?:19|20)\d{2}\b", metadata.text.strip())
        if year_match:
            year = int(year_match.group(0))
            break

    rating_elements = element.find_elements(
        "css selector", "span.ipc-rating-star--rating"
    )
    rating = None
    if rating_elements:
        rating_text = rating_elements[0].text.strip()
        try:
            rating = float(rating_text)
        except ValueError:
            logger.warning("Could not parse IMDb rating %r", rating_text)

    return {
        "title": title,
        "imdb_id": imdb_id,
        "poster_url": poster_url,
        "year": year,
        "rating": rating,
    }


def scrape_imdb_list(url: str) -> str:
    _validate_imdb_url(url)
    movies: list[Movie] = []
    seen_imdb_ids: set[str] = set()
    tvdb_token: str | None = None

    with _browser() as sb:
        sb.uc_open_with_reconnect(_url_for_page(url, 1), reconnect_time=4)
        try:
            sb.wait_for_element_present(ITEM_SELECTOR, timeout=20)
        except (NoSuchElementException, TimeoutException) as exc:
            raise RuntimeError(
                "IMDb did not display list items. Check that the URL is accessible "
                "and that IMDb did not show a sign-in or verification page."
            ) from exc

        page_options = sb.driver.find_elements("css selector", "#listPagination option")
        page_values = [
            int(value)
            for option in page_options
            if (value := option.get_attribute("value")) and value.isdigit()
        ]
        page_count = max(page_values, default=1)

        for page_number in range(1, page_count + 1):
            if page_number > 1:
                sb.driver.get(_url_for_page(url, page_number))
                try:
                    sb.wait_for_element_present(ITEM_SELECTOR, timeout=20)
                except (NoSuchElementException, TimeoutException) as exc:
                    raise RuntimeError(
                        f"IMDb did not load watchlist/list page {page_number}."
                    ) from exc

            stable_scrolls = 0
            previous_count = -1
            for _ in range(100):
                items = sb.find_elements(ITEM_SELECTOR)
                current_count = len(items)
                if current_count == previous_count:
                    stable_scrolls += 1
                    if stable_scrolls >= 2:
                        break
                else:
                    stable_scrolls = 0
                    previous_count = current_count

                sb.scroll_to_bottom()
                sb.sleep(1)
            else:
                raise RuntimeError(
                    f"IMDb kept loading items on page {page_number} beyond the "
                    "scraper's scroll limit."
                )

            items = sb.find_elements(ITEM_SELECTOR)
            page_movies: list[Movie] = []
            skipped_items = 0
            for item in items:
                movie_info = parse_movie_element(item)
                if not movie_info:
                    skipped_items += 1
                    continue
                if movie_info["imdb_id"] in seen_imdb_ids:
                    continue
                seen_imdb_ids.add(movie_info["imdb_id"])
                if _is_tv_series_element(item):
                    api_key = os.environ.get("TVDB_API_KEY")
                    if not api_key:
                        raise RuntimeError(
                            "TVDB_API_KEY is required to include TVDB IDs "
                            "for TV series."
                        )
                    if tvdb_token is None:
                        tvdb_token = _get_tvdb_token(api_key)
                    movie_info["tvdb_id"] = _lookup_tvdb_id(
                        movie_info["imdb_id"], tvdb_token
                    )
                page_movies.append(movie_info)

            if skipped_items:
                logger.warning(
                    "Skipped %d of %d IMDb items on page %d because their title "
                    "or ID was missing",
                    skipped_items,
                    len(items),
                    page_number,
                )
            if not page_movies:
                raise RuntimeError(
                    f"IMDb page {page_number} contained no new usable movie entries."
                )
            movies.extend(page_movies)

    if not movies:
        raise RuntimeError(
            "IMDb displayed list items, but none contained a usable title and IMDb ID."
        )

    return json.dumps(movies, indent=2)
