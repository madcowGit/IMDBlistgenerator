# IMDb List Generator

Scrape an IMDb list, user watchlist, or Top 250 chart and print its entries as
JSON. This JSON is in the Steven Lu custom list format, which can be directly used in Radarr or Sonarr (still WIP, because it needs TVDBId using their API).

It is intended to be deployed in docker on your own local network where Radarr/Sonarr can directly interact with it.

Note, because it open a browser and browses the IMDB site to scrape, it is not a very fast solution. But it works.

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

TV series entries include a `tvdb_id` obtained through the TVDB API. Set
`TVDB_API_KEY` in the environment to enable this lookup; scraping a TV series
without the key or if the TVDB request fails returns an error. If TVDB has no
matching series, `tvdb_id` is `null`. Movie entries do not require the key.

## Web API

Start the Flask server with:

```bash
imdb-list-generator-api
```

The server listens on `0.0.0.0:4444` by default. Set `PORT` to change the port.
Send an IMDb list, watchlist, or chart URL as JSON to `POST /api/scrape`:

```bash
curl -X POST http://localhost:4444/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.imdb.com/list/ls569954785/"}'
```

You can also initiate a scrape by opening `GET /api/scrape?url=...` in a
browser. For example, open this address to scrape the watchlist:

```text
http://localhost:4444/api/scrape?url=https%3A%2F%2Fwww.imdb.com%2Fuser%2Fp.ug53yeky7gegylcric634z6yta%2Fwatchlist
```

The response is a JSON array of scraped titles. `GET /` reports whether the
service is up, and `GET /health` reports API and scraper availability.

To return only items with a resolved TVDB ID, use
`GET /api/scrapetvseries?url=...`:

```text
http://localhost:4444/api/scrapetvseries?url=https%3A%2F%2Fwww.imdb.com%2Flist%2Fls569954785%2F
```

## Docker

Build and run the API container locally:

```bash
docker build -t imdb-list-generator .
docker run --rm -p 4444:4444 imdb-list-generator
```

For a published release, use `ghcr.io/madcowgit/imdblistgenerator:latest`
instead of `imdb-list-generator`.

The container exposes port `4444`; use `http://localhost:4444/health` to check
that it is ready. Published release images support `linux/amd64` and
`linux/arm64` under the same image tag.

Run the published image with Docker Compose by creating a `compose.yaml` file.
Set `IMDB_LIST_URLS` to one IMDb list, watchlist, or chart URL per line. Those
lists are refreshed immediately at startup and then every six hours by default.
Set `IMDB_CACHE_INTERVAL_HOURS` to change the refresh interval and
`IMDB_CACHE_DIR` to change where the JSON cache files are stored. Requests for
configured URLs are served from disk; other URLs continue to be scraped on
demand. A trailing slash on the configured URL is optional when requesting the
cache. A previous cache remains available if a refresh fails.

```yaml
services:
  imdb-list-generator:
    image: ghcr.io/madcowgit/imdblistgenerator:latest
    ports:
      - "4444:4444"
    environment:
      TVDB_API_KEY: ${TVDB_API_KEY:-}
      IMDB_LIST_URLS: |
        https://www.imdb.com/list/ls569954785/
        https://www.imdb.com/chart/top/
      IMDB_CACHE_INTERVAL_HOURS: ${IMDB_CACHE_INTERVAL_HOURS:-6}
      IMDB_CACHE_DIR: /app/cache
    volumes:
      - imdb-cache:/app/cache
    restart: unless-stopped

volumes:
  imdb-cache:
```

Set `TVDB_API_KEY` in your shell before starting Compose if a cached list
contains TV series:

```bash
export TVDB_API_KEY="your-tvdb-api-key"
```

The cache is persisted in the Docker-managed `imdb-cache` volume. This avoids
host-directory ownership mismatches with the container's non-root `app` user
(UID 10001). If you prefer a bind mount such as `./cache:/app/cache`, make sure
the host directory is writable by UID 10001; on Linux, you can run
`sudo chown -R 10001:10001 ./cache`.

Start the service and follow its logs with:

```bash
docker compose up -d
docker compose logs -f
```

Then send requests to `http://localhost:4444`. Stop the service with
`docker compose down`.

## Tests

The default test run uses deterministic unit tests and does not access IMDb:

```bash
python -m unittest discover -s tests -v
```

API tests can also be run separately:

```bash
python -m unittest discover -s tests -p 'test_api.py' -v
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

## Disclaimer

This project is a non-commercial project that has been entirely vibe-coded. The author is not responsible for any consequences due to the usage of this project. Use at your own risk. 
