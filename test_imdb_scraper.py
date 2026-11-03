import json
import re
import unittest

from imdb_scraper import scrape_imdb_list


IMDB_LIST_URL = "https://www.imdb.com/list/ls569954785/"
IMDB_WATCHLIST_URL = (
    "https://www.imdb.com/user/p.ug53yeky7gegylcric634z6yta/watchlist"
)
EXPECTED_MOVIE_FIELDS = {
    "title",
    "imdb_id",
    "poster_url",
    "year",
    "rating",
}


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
                    movie["poster_url"] is None
                    or isinstance(movie["poster_url"], str)
                )
                self.assertTrue(
                    movie["year"] is None or isinstance(movie["year"], int)
                )
                self.assertTrue(
                    movie["rating"] is None
                    or isinstance(movie["rating"], (int, float))
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


if __name__ == "__main__":
    unittest.main()
