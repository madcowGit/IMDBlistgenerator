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

The tests in `tests/` are live integration tests. They open a browser and access
IMDb, so they require network access and can be affected by changes or access
restrictions on IMDb:

```bash
python -m unittest discover -s tests -v
```

Run lint and formatting checks with:

```bash
ruff check .
ruff format --check .
```

## License

This project is licensed under the [MIT License](LICENSE).
