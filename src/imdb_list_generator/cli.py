import argparse

from imdb_list_generator.scraper import scrape_imdb_list

IMDB_LIST_URL = "https://www.imdb.com/list/ls569954785/"
IMDB_WATCHLIST_URL = "https://www.imdb.com/user/p.ug53yeky7gegylcric634z6yta/watchlist"
DEFAULT_IMDB_URL = IMDB_WATCHLIST_URL


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape an IMDb list or user watchlist and print JSON."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_IMDB_URL,
        help="IMDb list or watchlist URL (defaults to the configured watchlist)",
    )
    args = parser.parse_args()
    print(scrape_imdb_list(args.url))
