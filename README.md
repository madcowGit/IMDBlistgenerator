# IMDBlistgenerator (Dockerized API & Web App)

## Features
- **GitHub Actions CI/CD:** Automatically builds and pushes a Docker image to GitHub Container Registry (GHCR) when a GitHub release is published.
- **Docker Compose:** Configurable via environment variables (`IMDB_LIST_URLS`, `AUTO_SYNC_INTERVAL`).
- **REST API Endpoints:** Exposes scraped lists via JSON API for Sonarr, Radarr, or custom automation pipelines.

## REST API Endpoints
- `GET /api/lists` - Returns all auto-synced lists defined in `IMDB_LIST_URLS`.
- `GET /api/lists/list_1` - Returns specific synced list by ID.
- `POST /api/scrape` - On-demand scraping via JSON payload: `{"url": "https://www.imdb.com/chart/top/"}`
