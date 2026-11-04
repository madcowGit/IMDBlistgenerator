import unittest
from unittest.mock import patch, sentinel

from imdb_list_generator import cli
from imdb_list_generator.scraper import _validate_imdb_url, parse_movie_element

IMDB_LIST_URL = "https://www.imdb.com/list/ls569954785/"
IMDB_WATCHLIST_URL = "https://www.imdb.com/user/p.ug53yeky7gegylcric634z6yta/watchlist"
IMDB_TOP250_URL = "https://www.imdb.com/chart/top/"


class FakeElement:
    def __init__(self, text="", attributes=None, elements=None):
        self.text = text
        self.attributes = attributes or {}
        self.elements = elements or {}

    def get_attribute(self, name):
        return self.attributes.get(name)

    def find_elements(self, by, selector):
        return self.elements.get(selector, [])


class IMDbScraperTests(unittest.TestCase):
    def test_cli_requires_url_when_not_provided(self):
        with (
            patch("sys.argv", ["imdb-list-generator"]),
            patch.object(cli, "scrape_imdb_list") as scrape,
            self.assertRaisesRegex(SystemExit, "2"),
        ):
            cli.main()

        scrape.assert_not_called()

    def test_cli_passes_provided_url_to_scraper(self):
        url = "https://www.imdb.com/list/ls569954785/"
        with (
            patch("sys.argv", ["imdb-list-generator", url]),
            patch.object(cli, "scrape_imdb_list", return_value=sentinel.json),
            patch("builtins.print") as print_output,
        ):
            cli.main()

        print_output.assert_called_once_with(sentinel.json)

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


if __name__ == "__main__":
    unittest.main()
