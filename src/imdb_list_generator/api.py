import json
import os
from typing import Any

from flask import Flask, jsonify, request

from imdb_list_generator.scraper import scrape_imdb_list


def create_app() -> Flask:
    app = Flask(__name__)

    def scrape_url(url: str) -> Any:
        url = url.strip()
        if not url:
            return jsonify({"error": "IMDb list URL is required."}), 400

        try:
            result = scrape_imdb_list(url)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

        return jsonify(json.loads(result))

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

    return app


app = create_app()


def main() -> None:
    port = int(os.environ.get("PORT", "4444"))
    app.run(host="0.0.0.0", port=port)
