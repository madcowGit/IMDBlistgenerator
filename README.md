# IMDb List Generator

Scrape an IMDb list, user watchlist, or Top 250 chart and print its entries as
JSON. This JSON is in the Steven Lu custom list format, which can be directly used in Radarr or Sonarr .

It is intended to be deployed in docker on your own local network where Radarr/Sonarr can directly interact with it.

Note: because the scraper needs to open a browser window and browse the IMDB site to scrape, it is not a very fast solution. In the docker setup the scraped content is cached and updated every X hours. This means that there can be delay due to this mechanism

## Docker

The image is published on `ghcr.io/madcowgit/imdblistgenerator:latest`. Published release images support `linux/amd64` and `linux/arm64` under the same image tag.

### API end points

| API endpoint | Description |
| -------- | -------- | 
| `/health`    | general status info     | 
| `/api/scrape?url=...`     | Scrape IMDB (movies & TV series) list into JSON in Steven Lu custom format | 
| `/api/scrapetvseries?url=...`     | Scrape IMDB. Filter only TV Series and provide as Sonarr Custom List format | 

### Docker compose
Below is an example of a docker-compose.yml to run this container.

Set `IMDB_LIST_URLS` to one IMDb list, watchlist, or chart URL per line. Those
lists are refreshed immediately at startup and then every six hours by default.
Set `IMDB_CACHE_INTERVAL_HOURS` to change the refresh interval and
`IMDB_CACHE_DIR` to change where the JSON cache files are stored. Requests for
configured URLs are served from disk; other URLs continue to be scraped on
demand. A trailing slash on the configured URL is optional when requesting the
cache. A previous cache remains available if a refresh fails.

Set `TVDB_API_KEY` in your shell before starting Compose if a cached list
contains TV series. Be sure to use secrets or other methods to no put the API key directly in the compose file.

The container operates on port `4444`

```yaml
services:
  imdb-list-generator:
    image: ghcr.io/madcowgit/imdblistgenerator:latest
    ports:
      - "4444:4444"
    environment:
      TVDB_API_KEY: ${TVDB_API_KEY}
      IMDB_LIST_URLS: |
        https://www.imdb.com/list/ls569954785/
        https://www.imdb.com/chart/top/
      IMDB_CACHE_INTERVAL_HOURS: ${IMDB_CACHE_INTERVAL_HOURS}
      IMDB_CACHE_DIR: /app/cache
    volumes:
      - imdb-cache:/app/cache
    restart: unless-stopped

volumes:
  imdb-cache:
```

# Inner workings

## Python scaper

Use Python 3.11 or newer and install the project in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

SeleniumBase starts a browser. Chrome must be installed on your system when scraping.

## Run

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

This endpoint returns Sonarr custom-list entries with only `TvdbId` and
`Title` fields.

# License

This project is licensed under the [MIT License](LICENSE).

# Disclaimer

This project is a non-commercial project that has been entirely vibe-coded. The author is not responsible for any consequences due to the usage of this project. Use at your own risk. 
