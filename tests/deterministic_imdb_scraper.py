import json
import unittest
from contextlib import nullcontext
from unittest.mock import patch, sentinel

from imdb_list_generator import cli
from imdb_list_generator.scraper import (
    YEAR_SELECTOR,
    _is_tv_series_element,
    _lookup_tvdb_id,
    _validate_imdb_url,
    parse_movie_element,
    scrape_imdb_list,
)

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


class FakeDriver:
    def find_elements(self, by, selector):
        return []

    def get(self, url):
        pass


class FakeBrowser:
    def __init__(self, items):
        self.items = items
        self.driver = FakeDriver()

    def uc_open_with_reconnect(self, url, reconnect_time):
        pass

    def wait_for_element_present(self, selector, timeout):
        pass

    def find_elements(self, selector):
        return self.items

    def scroll_to_bottom(self):
        pass

    def sleep(self, seconds):
        pass


class IMDbScraperTests(unittest.TestCase):
    @staticmethod
    def make_item(metadata):
        title_link = FakeElement(
            text="Example Show",
            attributes={"href": "https://www.imdb.com/title/tt1234567/"},
        )
        return FakeElement(
            elements={
                "a.ipc-title-link-wrapper, a[href*='/title/tt']": [title_link],
                YEAR_SELECTOR: [FakeElement(text=value) for value in metadata],
            }
        )

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

    def test_is_tv_series_element_recognizes_tv_series_metadata(self):
        item = self.make_item(["2020–2024", "TV Series"])

        self.assertTrue(_is_tv_series_element(item))

    @patch("imdb_list_generator.scraper._lookup_tvdb_id", return_value=12345)
    @patch("imdb_list_generator.scraper._get_tvdb_token", return_value="token")
    def test_scrape_adds_tvdb_id_for_tv_series(self, get_token, lookup):
        item = self.make_item(["2020–2024", "TV Series"])
        browser = FakeBrowser([item])
        with (
            patch(
                "imdb_list_generator.scraper._browser",
                return_value=nullcontext(browser),
            ),
            patch.dict("os.environ", {"TVDB_API_KEY": "test-key"}),
        ):
            result = scrape_imdb_list(IMDB_LIST_URL)

        movie = json.loads(result)[0]
        self.assertEqual(movie["tvdb_id"], 12345)
        get_token.assert_called_once_with("test-key")
        lookup.assert_called_once_with("tt1234567", "token")

    def test_scrape_requires_tvdb_api_key_for_tv_series(self):
        item = self.make_item(["2020–2024", "TV Series"])
        browser = FakeBrowser([item])
        with (
            patch(
                "imdb_list_generator.scraper._browser",
                return_value=nullcontext(browser),
            ),
            patch.dict("os.environ", {}, clear=True),
            self.assertRaisesRegex(RuntimeError, "TVDB_API_KEY is required"),
        ):
            scrape_imdb_list(IMDB_LIST_URL)

    @patch("imdb_list_generator.scraper._get_tvdb_token")
    @patch("imdb_list_generator.scraper._lookup_tvdb_id")
    def test_scrape_does_not_lookup_tvdb_for_movie(self, lookup, get_token):
        item = self.make_item(["1994", "2h 22m"])
        browser = FakeBrowser([item])
        with patch(
            "imdb_list_generator.scraper._browser", return_value=nullcontext(browser)
        ):
            movie = json.loads(scrape_imdb_list(IMDB_LIST_URL))[0]

        self.assertNotIn("tvdb_id", movie)
        lookup.assert_not_called()
        get_token.assert_not_called()

    @patch("imdb_list_generator.scraper._tvdb_request")
    def test_lookup_tvdb_id_extracts_remote_id_match(self, tvdb_request):
        tvdb_request.return_value = {
            "status": "success",
            "data": [{"series": {"id": 12345}}],
        }

        self.assertEqual(_lookup_tvdb_id("tt1234567", "token"), 12345)
        tvdb_request.assert_called_once_with(
            "https://api4.thetvdb.com/v4/search/remoteid/tt1234567",
            token="token",
        )


if __name__ == "__main__":
    unittest.main()
