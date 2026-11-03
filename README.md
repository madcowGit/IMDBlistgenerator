# IMDBlistgenerator

Dockerized IMDb list scraper and exporter that fetches titles from public IMDb list pages, extracts metadata, and exposes download files and JSON API endpoints.

## Features

- Scrapes public IMDb list, chart, and title-search pages using Selenium + Chromium
- Follows IMDb's next-page links with a configurable page limit and deduplicates titles across pages
- Uses page structure and `ItemList` JSON-LD with conservative parsing fallbacks
- Stops and reports clearly if IMDb presents a human-verification page; it does not attempt to bypass verification or access controls
- Exports results as CSV, JSON, and TXT (IMDb IDs)
- Runs as a Flask web app
- Supports automatic list syncing from environment variables
- Includes a simple health endpoint for container monitoring
- Works with Docker Compose for local or server deployment

## Run with Docker Compose

1. Copy the sample environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set a secure `FLASK_SECRET_KEY`.

3. Start the app:

   ```bash
   docker compose up --build -d
   ```

4. View the app at `http://localhost:5000/` and check `http://localhost:5000/healthz` for container health.

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `FLASK_SECRET_KEY` | required | Secret key used by Flask for session and flash handling |
| `PORT` | `5000` | Port exposed inside the container and mapped by Docker |
| `IMDB_LIST_URLS` | empty | Comma-separated IMDb list/chart/search URLs to auto-sync |
| `AUTO_SYNC_INTERVAL` | `3600` | Refresh interval in seconds for automatic sync; use `0` to disable |
| `IMDB_MAX_PAGES` | `100` | Maximum number of next-linked pages fetched per submitted URL |
| `IMDB_REQUEST_DELAY` | `1.0` | Minimum delay in seconds between paginated pages (values below 0.5 are raised to 0.5) |
| `HOST_PORT` | `5000` | Host port used when running via Docker Compose |

## API endpoints

- `GET /` — Web UI for submitting IMDb URLs and exporting files
- `GET /healthz` — Basic app health check JSON
- `GET /api/lists` — Lists all auto-synced IMDb lists
- `GET /api/lists/<list_id>` — Returns a specific synced list
- `POST /api/scrape` — Scrapes a supported IMDb list URL and returns JSON payload
- `GET /download/<filename>` — Downloads exported files from the output directory

Example API call:

```bash
curl -X POST http://localhost:5000/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.imdb.com/list/ls000000000/"}'
```

Supported URL types include `/list/...`, `/chart/...`, `/search/title?...`, and `/user/...` on `imdb.com` or `www.imdb.com`.

## Output files

Generated files are saved under `/app/output` inside the container and persist via the named Docker volume `imdb_data`.

Files include CSV metadata, JSON objects, and a TXT list containing IMDb IDs.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_SECRET_KEY=change-me
python app.py
```

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:FLASK_SECRET_KEY = "change-me"
python app.py
```

Then open `http://localhost:5000`.

## Notes

- IMDb page structure can change; selector and parser updates may be needed over time.
- Scraping is limited to publicly accessible pages. If IMDb presents a verification or access-denied page, the app stops rather than trying to evade it. Follow IMDb's terms and applicable rate limits.
- Selenium + Chromium is required; the Docker image installs both.
- Keep `FLASK_SECRET_KEY` out of version control; use `.env` and do not commit it.
