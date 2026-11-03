# IMDb Steven Lu Format Scraper API

A Dockerized FastAPI application using `undetected-chromedriver` and `Xvfb` to scrape IMDb lists/charts and export them in the Steven Lu JSON format (compatible with custom list importers like Radarr).

## Features

- Uses `undetected-chromedriver` running in a virtual frame buffer (`Xvfb`) to bypass anti-bot challenges.
- Parses IMDb lists into Steven Lu custom list JSON format (`title`, `imdb_id`, `poster_url`, `year`).
- Fast REST API interface powered by FastAPI and Uvicorn.
- Automated testing workflow via GitHub Actions.

## Development with a Dev Container

Open the repository in VS Code and choose **Reopen in Container** (or open it in GitHub Codespaces). The container builds from the project Dockerfile, installs the Python and Chrome dependencies, and starts the API. Port `8000` is forwarded automatically; the API docs are available at `http://localhost:8000/docs`.

## Output Schema (Steven Lu Format)

```json
[
  {
    "title": "The Shawshank Redemption",
    "imdb_id": "tt0111161",
    "poster_url": "[https://m.media-amazon.com/images/M/MV5BMDFkYT43](https://m.media-amazon.com/images/M/MV5BMDFkYT43)...",
    "year": "1994"
  }
]