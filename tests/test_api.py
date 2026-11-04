import json
import unittest
from unittest.mock import patch

from imdb_list_generator.api import create_app


class IMDbApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_root_reports_service_is_up(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "up"})

    def test_healthcheck_reports_api_and_scraper(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "status": "healthy",
                "checks": {"api": "ok", "scraper": "available"},
            },
        )

    @patch("imdb_list_generator.api.scrape_imdb_list")
    def test_scrape_endpoint_returns_scraped_json(self, scrape):
        expected = [{"title": "Sample", "imdb_id": "tt1234567"}]
        scrape.return_value = json.dumps(expected)

        response = self.client.post(
            "/api/scrape",
            json={"url": "https://www.imdb.com/list/ls123456789/"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)
        scrape.assert_called_once_with("https://www.imdb.com/list/ls123456789/")

    @patch("imdb_list_generator.api.scrape_imdb_list")
    def test_browser_scrape_endpoint_returns_scraped_json(self, scrape):
        expected = [{"title": "Sample", "imdb_id": "tt1234567"}]
        scrape.return_value = json.dumps(expected)

        response = self.client.get(
            "/api/scrape",
            query_string={
                "url": "https://www.imdb.com/user/p.ug53yeky7gegylcric634z6yta/watchlist"
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)
        scrape.assert_called_once_with(
            "https://www.imdb.com/user/p.ug53yeky7gegylcric634z6yta/watchlist"
        )

    def test_browser_scrape_endpoint_requires_url(self):
        response = self.client.get("/api/scrape")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "IMDb list URL is required."})

    @patch("imdb_list_generator.api.scrape_imdb_list")
    def test_browser_tv_series_endpoint_returns_only_items_with_tvdb_ids(self, scrape):
        expected = [
            {"title": "Series", "imdb_id": "tt1111111", "tvdb_id": 12345},
            {"title": "Another series", "imdb_id": "tt2222222", "tvdb_id": "67890"},
        ]
        scrape.return_value = json.dumps(
            [
                *expected[:1],
                {"title": "Movie", "imdb_id": "tt3333333"},
                {"title": "Unmatched series", "imdb_id": "tt4444444", "tvdb_id": None},
                expected[1],
            ]
        )

        response = self.client.get(
            "/api/scrapetvseries",
            query_string={"url": "https://www.imdb.com/list/ls123456789/"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)
        scrape.assert_called_once_with("https://www.imdb.com/list/ls123456789/")

    def test_browser_tv_series_endpoint_requires_url(self):
        response = self.client.get("/api/scrapetvseries")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "IMDb list URL is required."})

    def test_scrape_endpoint_requires_json_url(self):
        for payload in ({}, {"url": 42}, {"other": "value"}):
            with self.subTest(payload=payload):
                response = self.client.post("/api/scrape", json=payload)

                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

    @patch("imdb_list_generator.api.scrape_imdb_list")
    def test_scrape_endpoint_returns_bad_request_for_invalid_url(self, scrape):
        scrape.side_effect = ValueError("URL must be an IMDb list")

        response = self.client.post("/api/scrape", json={"url": "https://example.com"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "URL must be an IMDb list"})

    @patch("imdb_list_generator.api.scrape_imdb_list")
    def test_scrape_endpoint_returns_bad_gateway_when_scraping_fails(self, scrape):
        scrape.side_effect = RuntimeError("IMDb is unavailable")

        response = self.client.post(
            "/api/scrape", json={"url": "https://www.imdb.com/list/ls123456789/"}
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json(), {"error": "IMDb is unavailable"})


if __name__ == "__main__":
    unittest.main()
