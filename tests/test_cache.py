import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from imdb_list_generator.cache import (
    CacheNotReadyError,
    ScrapeCache,
    create_cache_from_environment,
)


class ScrapeCacheTests(unittest.TestCase):
    def test_refresh_writes_json_that_can_be_loaded(self):
        expected = [{"title": "Example", "imdb_id": "tt1234567"}]
        with tempfile.TemporaryDirectory() as cache_dir:
            cache = ScrapeCache(
                ["https://www.imdb.com/list/ls123456789/"],
                cache_dir,
                6,
                scraper=Mock(return_value=json.dumps(expected)),
            )

            with self.assertRaises(CacheNotReadyError):
                cache.load(cache.urls[0])

            cache.refresh_once()

            self.assertEqual(cache.load(cache.urls[0]), expected)
            self.assertEqual(len(list(Path(cache_dir).glob("*.json"))), 1)

    def test_cache_matches_configured_url_with_or_without_trailing_slash(self):
        configured_url = (
            "https://www.imdb.com/user/p.ug53yeky7gegylcric634z6yta/watchlist/"
        )
        requested_url = configured_url.rstrip("/")
        expected = [{"title": "Cached", "imdb_id": "tt1234567"}]
        with tempfile.TemporaryDirectory() as cache_dir:
            cache = ScrapeCache(
                [configured_url],
                cache_dir,
                6,
                scraper=Mock(return_value=json.dumps(expected)),
            )

            cache.refresh_once()

            self.assertTrue(cache.is_configured(requested_url))
            self.assertEqual(cache.load(requested_url), expected)

    def test_failed_refresh_keeps_the_previous_cache(self):
        expected = [{"title": "Example", "imdb_id": "tt1234567"}]
        scraper = Mock(
            side_effect=[json.dumps(expected), RuntimeError("IMDb is unavailable")]
        )
        with tempfile.TemporaryDirectory() as cache_dir:
            cache = ScrapeCache(
                ["https://www.imdb.com/list/ls123456789/"],
                cache_dir,
                6,
                scraper=scraper,
            )
            cache.refresh_once()

            with self.assertLogs("imdb_list_generator.cache", level="ERROR"):
                cache.refresh_once()

            self.assertEqual(cache.load(cache.urls[0]), expected)

    def test_cache_configuration_uses_newline_urls_and_six_hour_default(self):
        with (
            patch.dict(
                "os.environ",
                {
                    "IMDB_LIST_URLS": (
                        "https://www.imdb.com/list/ls123456789/\n"
                        "https://www.imdb.com/chart/top/\n"
                    )
                },
                clear=True,
            ),
            tempfile.TemporaryDirectory() as cache_dir,
            patch.dict("os.environ", {"IMDB_CACHE_DIR": cache_dir}),
        ):
            cache = create_cache_from_environment()

        self.assertIsNotNone(cache)
        assert cache is not None
        self.assertEqual(len(cache.urls), 2)
        self.assertEqual(cache.refresh_interval_seconds, 6 * 60 * 60)
        self.assertEqual(cache.cache_dir, Path(cache_dir))

    def test_cache_configuration_rejects_nonpositive_refresh_interval(self):
        for interval in ("0", "nan", "inf"):
            with self.subTest(interval=interval):
                with (
                    patch.dict(
                        "os.environ",
                        {
                            "IMDB_LIST_URLS": (
                                "https://www.imdb.com/list/ls123456789/"
                            ),
                            "IMDB_CACHE_INTERVAL_HOURS": interval,
                        },
                        clear=True,
                    ),
                    self.assertRaisesRegex(ValueError, "must be greater than zero"),
                ):
                    create_cache_from_environment()
