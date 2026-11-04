# IMDb List Generator

Scrape an IMDb list, user watchlist, or Top 250 chart and print its entries as
JSON. This JSON is in the Steven Lu custom list format, which can be directly used in Radarr or Sonarr.

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

```bash
python -m imdb_list_generator
```

Provide an IMDb list, watchlist, or chart URL. Running the command without a URL
returns an error stating that an IMDb list URL is required:

```bash
python -m imdb_list_generator "https://www.imdb.com/list/ls569954785/"
python -m imdb_list_generator "https://www.imdb.com/chart/top/"
```

The installed `imdb-list-generator` command can be used in place of
`python -m imdb_list_generator`.

## Tests

The default test run uses deterministic unit tests and does not access IMDb:

```bash
python -m unittest discover -s tests -v
```

Live integration tests are in `tests/live_imdb_scraper.py`. They open a browser
and can be affected by network access restrictions or changes on IMDb. Run them
explicitly with:

```bash
python -m unittest discover -s tests -p 'live_*.py' -v
```

Run lint and formatting checks with:

```bash
ruff check .
ruff format --check .
```

## License

This project is licensed under the [MIT License](LICENSE).
