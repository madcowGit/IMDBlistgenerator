import argparse

from imdb_list_generator.scraper import scrape_imdb_list


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape an IMDb list, watchlist, or Top 250 chart and print JSON."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="IMDb list, watchlist, or Top 250 chart URL",
    )
    args = parser.parse_args()
    if not args.url:
        parser.error("IMDb list URL is required")
    print(scrape_imdb_list(args.url))
