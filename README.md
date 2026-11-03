# IMDBlistgenerator

Dockerized IMDb list scraper and exporter that fetches titles from IMDb list pages, extracts metadata, and exposes download files and JSON API endpoints.

## Features

- Scrapes IMDb list pages using Selenium + Chromium
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

4. View the app:

   ```text
   http://localhost:5000/
   ```

5. Check the health endpoint:

   ```text
   http://localhost:5000/healthz
   ```

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `FLASK_SECRET_KEY` | required | Secret key used by Flask for session and flash handling |
| `PORT` | `5000` | Port exposed inside the container and mapped by Docker |
| `IMDB_LIST_URLS` | `https://www.imdb.com/chart/top/` | Comma-separated IMDb URLs to auto-sync |
| `AUTO_SYNC_INTERVAL` | `3600` | Refresh interval in seconds for automatic sync; use `0` to disable |
| `HOST_PORT` | `5000` | Host port used when running via Docker Compose |

## API endpoints

- `GET /` — Web UI for submitting IMDb URLs and exporting files
- `GET /healthz` — Basic app health check JSON
- `GET /api/lists` — Lists all auto-synced IMDb lists
- `GET /api/lists/<list_id>` — Returns a specific synced list
- `POST /api/scrape` — Scrapes an IMDb list URL and returns JSON payload
- `GET /download/<filename>` — Downloads exported files from the output directory

Example API call:

```bash
curl -X POST http://localhost:5000/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.imdb.com/chart/top/"}'
```

## Output files

Generated files are saved under `/app/output` inside the container and persist via the named Docker volume `imdb_data`.

Files include:

- CSV export with title metadata
- JSON export with full objects
- TXT export containing only IMDb IDs

## Local development

If you want to run the app without Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_SECRET_KEY=change-me
python app.py
```

Then open `http://localhost:5000`.

## Notes

- IMDb page structure can change over time and may require scraper selector updates.
- Selenium + Chromium is required for scraping; the Docker image installs both.
- Keep `FLASK_SECRET_KEY` out of version control; use `.env` and do not commit it.

## GitHub workflow

A Ruff workflow can be added to CI to check Python lint and formatting automatically on push and pull requests.
