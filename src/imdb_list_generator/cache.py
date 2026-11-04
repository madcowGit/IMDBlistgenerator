import hashlib
import json
import logging
import math
import os
import tempfile
from pathlib import Path
from threading import Event, Thread
from typing import Any, Callable

from imdb_list_generator.scraper import _validate_imdb_url, scrape_imdb_list

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = "/app/cache"
DEFAULT_REFRESH_INTERVAL_HOURS = 6.0


class CacheNotReadyError(RuntimeError):
    pass


class ScrapeCache:
    def __init__(
        self,
        urls: list[str],
        cache_dir: str | Path,
        refresh_interval_hours: float,
        scraper: Callable[[str], str] = scrape_imdb_list,
    ) -> None:
        self.urls = tuple(dict.fromkeys(urls))
        self.cache_dir = Path(cache_dir)
        self.refresh_interval_seconds = refresh_interval_hours * 60 * 60
        self.scraper = scraper
        self._stop_event = Event()
        self._thread: Thread | None = None

        if not math.isfinite(refresh_interval_hours) or refresh_interval_hours <= 0:
            raise ValueError("IMDB_CACHE_INTERVAL_HOURS must be greater than zero.")
        for url in self.urls:
            _validate_imdb_url(url)

    def is_configured(self, url: str) -> bool:
        return url in self.urls

    def load(self, url: str) -> list[Any]:
        if not self.is_configured(url):
            raise ValueError("URL is not configured for caching.")

        cache_path = self._cache_path(url)
        try:
            with cache_path.open(encoding="utf-8") as cache_file:
                cached_data = json.load(cache_file)
        except FileNotFoundError as exc:
            raise CacheNotReadyError(
                "No cached results are available for this URL yet."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception("Could not read cached IMDb results from %s", cache_path)
            raise RuntimeError("Cached IMDb results could not be read.") from exc

        if not isinstance(cached_data, list):
            logger.error("Cached IMDb results in %s are not a JSON list", cache_path)
            raise RuntimeError("Cached IMDb results are invalid.")
        return cached_data

    def start(self) -> None:
        if not self.urls or self._thread is not None:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._thread = Thread(
            target=self._refresh_loop,
            name="imdb-cache-refresh",
            daemon=True,
        )
        self._thread.start()

    def refresh_once(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        for url in self.urls:
            try:
                result = self.scraper(url)
                if not isinstance(json.loads(result), list):
                    raise RuntimeError("Scraper result must be a JSON list.")
                self._write(url, result)
            except Exception:
                logger.exception("Could not refresh IMDb cache for %s", url)

    def _refresh_loop(self) -> None:
        while not self._stop_event.is_set():
            self.refresh_once()
            self._stop_event.wait(self.refresh_interval_seconds)

    def _cache_path(self, url: str) -> Path:
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def _write(self, url: str, data: str) -> None:
        cache_path = self._cache_path(url)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.cache_dir,
                prefix=f".{cache_path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as cache_file:
                temp_path = cache_file.name
                cache_file.write(data)
            os.replace(temp_path, cache_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)


def create_cache_from_environment() -> ScrapeCache | None:
    urls = [
        url.strip()
        for url in os.environ.get("IMDB_LIST_URLS", "").splitlines()
        if url.strip()
    ]
    if not urls:
        return None

    try:
        refresh_interval_hours = float(
            os.environ.get(
                "IMDB_CACHE_INTERVAL_HOURS",
                str(DEFAULT_REFRESH_INTERVAL_HOURS),
            )
        )
    except ValueError as exc:
        raise ValueError("IMDB_CACHE_INTERVAL_HOURS must be a number.") from exc

    return ScrapeCache(
        urls,
        os.environ.get("IMDB_CACHE_DIR", DEFAULT_CACHE_DIR),
        refresh_interval_hours,
    )
