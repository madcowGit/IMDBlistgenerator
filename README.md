# IMDb List Generator

Scrape IMDb lists, user watchlists, or the Top 250 chart and convert them into JSON formats compatible with Radarr and Sonarr.

This tool is designed to run in Docker on your local network, allowing Radarr and Sonarr to sync with IMDb lists that aren't natively supported or to provide more frequent updates.

## Features

- **Format Compatibility**: 
  - **Radarr**: Outputs in the Steven Lu custom list format.
  - **Sonarr**: Filters for TV series and outputs in the Sonarr Custom List format (including TVDB ID lookup).
- **Caching**: Configured URLs are scraped in the background and cached to disk for instant responses.
- **On-demand Scraping**: URLs not in the cache configuration can still be scraped on-demand.
- **Architecture Support**: Docker images support `linux/amd64` and `linux/arm64`.

## Setup in Radarr & Sonarr

Configure your lists as follows (replace `localhost` with your server's IP if necessary):

| Program | List Type | List URL |
| -------- | -------- | -------- | 
| **Radarr** | StevenLu Custom | `http://localhost:4444/api/scrape?url=IMDB_URL` |
| **Sonarr** | Custom List | `http://localhost:4444/api/scrapetvseries?url=IMDB_URL` |

> [!NOTE]
> When first starting the container with new IMDb URLs, give it a few minutes to perform the initial scrape before Radarr/Sonarr try to pull the data.

## Configuration

### Environment Variables

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `IMDB_LIST_URLS` | Multi-line list of IMDb URLs to cache automatically. | None |
| `IMDB_CACHE_INTERVAL_HOURS` | How often to refresh the cached lists. | `6` |
| `IMDB_CACHE_DIR` | Directory where JSON cache files are stored. | `/app/cache` |
| `TVDB_API_KEY` | Required for TV series (Sonarr). Used to map IMDb IDs to TVDB IDs. | None |
| `PORT` | The port the Web API listens on. | `4444` |
| `IMDB_USE_SYSTEM_CHROMIUM` | Set to `1` to use a pre-installed Chromium (useful for custom Docker builds). | `0` |

### Docker Compose

The official image is `ghcr.io/madcowgit/imdblistgenerator:latest`.

```yaml
services:
  imdb-list-generator:
    image: ghcr.io/madcowgit/imdblistgenerator:latest
    container_name: imdb-list-generator
    ports:
      - "4444:4444"
    environment:
      - TVDB_API_KEY=your_api_key_here
      - IMDB_LIST_URLS=|
          https://www.imdb.com/list/ls569954785/
          https://www.imdb.com/chart/top/
      - IMDB_CACHE_INTERVAL_HOURS=6
    volumes:
      - ./cache:/app/cache
    restart: unless-stopped
```

## API Endpoints

| Endpoint | Method | Description |
| -------- | ------ | ----------- |
| `/health` | GET | Returns health status of the API and Scraper. |
| `/api/scrape` | GET/POST | Returns all entries (Movies & TV) in Steven Lu format. |
| `/api/scrapetvseries` | GET | Returns TV series only, mapped for Sonarr (`TvdbId`, `Title`). |

### Usage Examples

**Scrape a specific list via GET:**
```text
http://localhost:4444/api/scrape?url=https://www.imdb.com/chart/top/
```

**Scrape via POST (JSON):**
```bash
curl -X POST http://localhost:4444/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.imdb.com/list/ls569954785/"}'
```

## Local Development

### Requirements
- Python 3.11+
- Chrome/Chromium installed (for SeleniumBase)

### Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Running the CLI
You can scrape a list directly to your terminal:
```bash
imdb-list-generator "https://www.imdb.com/chart/top/"
```

### Running the API
```bash
imdb-list-generator-api
```

## License

This project is licensed under the [MIT License](LICENSE).

## Disclaimer

This project is a non-commercial, community-driven tool. The author is not responsible for any consequences resulting from its use. Use at your own risk.