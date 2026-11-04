import json
import os
from typing import Any

from flask import Flask, jsonify, request

from imdb_list_generator.cache import (
    CacheNotReadyError,
    create_cache_from_environment,
)
from imdb_list_generator.scraper import _validate_imdb_url, scrape_imdb_list


def create_app() -> Flask:
    app = Flask(__name__)
    scrape_cache = create_cache_from_environment()
    app.extensions["imdb_scrape_cache"] = scrape_cache
    if scrape_cache is not None:
        scrape_cache.start()

    def scrape_url(url: str, *, tvdb_only: bool = False) -> Any:
        url = url.strip()
        if not url:
            return jsonify({"error": "IMDb list URL is required."}), 400

        try:
            if scrape_cache is not None and scrape_cache.is_configured(url):
                _validate_imdb_url(url)
                items = scrape_cache.load(url)
            else:
                items = json.loads(scrape_imdb_list(url))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except CacheNotReadyError as exc:
            return jsonify({"error": str(exc)}), 503
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

        if tvdb_only:
            items = [
                {"TvdbId": item["tvdb_id"], "Title": item["title"]}
                for item in items
                if isinstance(item, dict)
                and item.get("tvdb_id") is not None
                and isinstance(item.get("title"), str)
            ]
        return jsonify(items)

    @app.get("/")
    def status() -> Any:
        return jsonify({"status": "up"})

    @app.get("/health")
    def healthcheck() -> Any:
        checks = {
            "api": "ok",
            "scraper": "available" if callable(scrape_imdb_list) else "unavailable",
        }
        is_healthy = all(value != "unavailable" for value in checks.values())
        status_code = 200 if is_healthy else 503
        return (
            jsonify(
                {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "checks": checks,
                }
            ),
            status_code,
        )

    @app.post("/api/scrape")
    def scrape() -> Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
            return jsonify({"error": "Request JSON must contain a string 'url'."}), 400

        return scrape_url(payload["url"])

    @app.get("/api/scrape")
    def scrape_from_browser() -> Any:
        url = request.args.get("url")
        if url is None:
            return jsonify({"error": "IMDb list URL is required."}), 400

        return scrape_url(url)

    @app.get("/api/scrapetvseries")
    def scrape_tv_series_from_browser() -> Any:
        url = request.args.get("url")
        if url is None:
            return jsonify({"error": "IMDb list URL is required."}), 400

        return scrape_url(url, tvdb_only=True)

    return app


app = create_app()


def main() -> None:
    port = int(os.environ.get("PORT", "4444"))
    app.run(host="0.0.0.0", port=port)
