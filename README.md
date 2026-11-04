# IMDb List Generator

Scrape an IMDb list, user watchlist, or Top 250 chart and print its entries as
JSON.

## Install

Use Python 3.11 or newer and install the project in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

SeleniumBase starts a browser when scraping. Install Chrome or Chromium on the
machine running the scraper.

## Run

The configured watchlist is the default:

```bash
python -m imdb_list_generator
```

Pass an IMDb list, watchlist, or chart URL to scrape a different page:

```bash
python -m imdb_list_generator "https://www.imdb.com/list/ls569954785/"
python -m imdb_list_generator "https://www.imdb.com/chart/top/"
```

The installed `imdb-list-generator` command can be used in place of
`python -m imdb_list_generator`.

## Tests

The default test run uses deterministic unit tests and does not access IMDb.
Live integration tests open a browser and can be affected by network access
restrictions or changes on IMDb. Run them explicitly with:

```bash
RUN_IMDB_INTEGRATION_TESTS=1 python -m unittest discover -s tests -v
```

Run lint and formatting checks with:

```bash
ruff check .
ruff format --check .
```

## License

This project is licensed under the [MIT License](LICENSE).
