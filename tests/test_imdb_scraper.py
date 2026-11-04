import json
import os
import re
import unittest

from imdb_list_generator.scraper import (
    _validate_imdb_url,
    parse_movie_element,
    scrape_imdb_list,
)

IMDB_LIST_URL = "https://www.imdb.com/list/ls569954785/"
IMDB_WATCHLIST_URL = "https://www.imdb.com/user/p.ug53yeky7gegylcric634z6yta/watchlist"
IMDB_TOP250_URL = "https://www.imdb.com/chart/top/"
EXPECTED_MOVIE_FIELDS = {
    "title",
    "imdb_id",
    "poster_url",
    "year",
    "rating",
}


class FakeElement:
    def __init__(self, text="", attributes=None, elements=None):
        self.text = text
        self.attributes = attributes or {}
        self.elements = elements or {}

    def get_attribute(self, name):
        return self.attributes.get(name)

    def find_elements(self, by, selector):
        return self.elements.get(selector, [])


class IMDbScraperUnitTests(unittest.TestCase):
    def test_validate_accepts_supported_imdb_urls(self):
        for url in (IMDB_LIST_URL, IMDB_WATCHLIST_URL, IMDB_TOP250_URL):
            with self.subTest(url=url):
                _validate_imdb_url(url)

    def test_validate_rejects_non_imdb_and_unsupported_urls(self):
        invalid_urls = (
            "https://imdb.com.example.org/list/ls123/",
            "https://www.imdb.com/title/tt0111161/",
        )
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                _validate_imdb_url(url)

    def test_parse_movie_element_extracts_movie_fields(self):
        empty_overlay = FakeElement(
            attributes={"href": "https://www.imdb.com/title/tt0111161/"}
        )
        title_link = FakeElement(
            text="1. The Shawshank Redemption",
            attributes={"href": "https://www.imdb.com/title/tt0111161/"},
        )
        image = FakeElement(attributes={"src": "https://example.test/poster.jpg"})
        year = FakeElement(text="1994")
        rating = FakeElement(text="9.3")
        card = FakeElement(
            elements={
                "a.ipc-title-link-wrapper, a[href*='/title/tt']": [
                    empty_overlay,
                    title_link,
                ],
                "img.ipc-image": [image],
                (
                    "span.dli-title-metadata-item, "
                    "li.cli-title-metadata-item, "
                    "span.cli-title-metadata-item, "
                    "li.ipc-inline-list__item"
                ): [year],
                "span.ipc-rating-star--rating": [rating],
            }
        )

        self.assertEqual(
            parse_movie_element(card),
            {
                "title": "The Shawshank Redemption",
                "imdb_id": "tt0111161",
                "poster_url": "https://example.test/poster.jpg",
                "year": 1994,
                "rating": 9.3,
            },
        )


@unittest.skipUnless(
    os.environ.get("RUN_IMDB_INTEGRATION_TESTS") == "1",
    "Set RUN_IMDB_INTEGRATION_TESTS=1 to run live IMDb browser tests",
)
class IMDbScraperIntegrationTests(unittest.TestCase):
    def test_scrapes_list_as_valid_json(self):
        json_output = scrape_imdb_list(IMDB_LIST_URL)
        movies = json.loads(json_output)

        self.assertIsInstance(movies, list)
        self.assertTrue(movies, "IMDb list should contain at least one movie")

        for movie in movies:
            with self.subTest(imdb_id=movie.get("imdb_id")):
                self.assertEqual(set(movie), EXPECTED_MOVIE_FIELDS)
                self.assertIsInstance(movie["title"], str)
                self.assertTrue(movie["title"].strip())
                self.assertRegex(movie["imdb_id"], re.compile(r"^tt\d+$"))
                self.assertTrue(
                    movie["poster_url"] is None or isinstance(movie["poster_url"], str)
                )
                self.assertTrue(movie["year"] is None or isinstance(movie["year"], int))
                self.assertTrue(
                    movie["rating"] is None or isinstance(movie["rating"], (int, float))
                )

    def test_scrapes_at_least_260_watchlist_entries(self):
        json_output = scrape_imdb_list(IMDB_WATCHLIST_URL)
        movies = json.loads(json_output)

        self.assertGreaterEqual(len(movies), 260)
        self.assertEqual(
            len({movie["imdb_id"] for movie in movies}),
            len(movies),
            "Watchlist entries should have unique IMDb IDs",
        )

    def test_scrapes_top_250_chart_entries(self):
        json_output = scrape_imdb_list(IMDB_TOP250_URL)
        movies = json.loads(json_output)

        self.assertEqual(len(movies), 250)
        self.assertEqual(
            len({movie["imdb_id"] for movie in movies}),
            250,
            "Top 250 chart entries should have unique IMDb IDs",
        )


if __name__ == "__main__":
    unittest.main()
