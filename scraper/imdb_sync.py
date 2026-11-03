import os
import uuid
import logging
from urllib.parse import urlparse

from flask import Flask, render_template, request, jsonify, send_from_directory, flash, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler

from scraper.imdb_sync import IMDbSyncScraper
from scraper.utils import save_to_csv, save_to_json, save_to_txt_ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key-change-this")

OUTPUT_DIR = os.path.join(app.root_path, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ENV_LIST_CACHE = {}


def is_valid_imdb_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return bool(parsed.scheme in {"http", "https"} and parsed.netloc and "imdb.com" in parsed.netloc)


def sync_env_lists():
    """Syncs IMDb lists specified in IMDB_LIST_URLS environment variable."""
    urls_raw = os.getenv("IMDB_LIST_URLS", "")
    if not urls_raw:
        return []

    urls = [u.strip() for u in urls_raw.split(",") if u.strip()]
    logger.info(f"Starting scheduled sync for {len(urls)} environment list(s)...")

    scraper = None
    synced = []
    try:
        scraper = IMDbSyncScraper(headless=True)
        for idx, url in enumerate(urls, start=1):
            if not is_valid_imdb_url(url):
                logger.warning("Skipping invalid IMDb URL in IMDB_LIST_URLS: %s", url)
                continue

            items = scraper.fetch_list_items(url)
            if not items:
                logger.warning("No items extracted for environment list %s (%s)", idx, url)
                continue

            key = f"list_{idx}"
            ENV_LIST_CACHE[key] = {
                "url": url,
                "count": len(items),
                "items": items,
            }
            save_to_json(items, os.path.join(OUTPUT_DIR, f"{key}.json"))
            save_to_txt_ids(items, os.path.join(OUTPUT_DIR, f"{key}_ids.txt"))
            save_to_csv(items, os.path.join(OUTPUT_DIR, f"{key}.csv"))
            synced.append(key)
    except Exception as e:
        logger.exception("Error during env list sync: %s", e)
    finally:
        if scraper:
            scraper.close()

    return synced


interval = int(os.getenv("AUTO_SYNC_INTERVAL", "3600"))
scheduler = BackgroundScheduler()
if interval > 0:
    scheduler.add_job(func=sync_env_lists, trigger="interval", seconds=interval)
    scheduler.start()

try:
    sync_env_lists()
except Exception as e:
    logger.warning(f"Initial startup sync failed: {e}")


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({
        "status": "ok",
        "lists": len(ENV_LIST_CACHE),
        "output_dir": OUTPUT_DIR,
    })


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url", "").strip()
        export_format = request.form.get("format", "all")

        if not is_valid_imdb_url(url):
            flash("Please enter a valid IMDb URL.", "danger")
            return redirect(url_for("index"))

        session_id = str(uuid.uuid4())[:8]

        scraper = None
        try:
            scraper = IMDbSyncScraper(headless=True)
            items = scraper.fetch_list_items(url)

            if not items:
                flash("No items could be extracted from the URL provided.", "warning")
                return redirect(url_for("index"))

            files_created = {}
            if export_format in ["csv", "all"]:
                filename = f"imdb_{session_id}.csv"
                save_to_csv(items, os.path.join(OUTPUT_DIR, filename))
                files_created["csv"] = filename

            if export_format in ["json", "all"]:
                filename = f"imdb_{session_id}.json"
                save_to_json(items, os.path.join(OUTPUT_DIR, filename))
                files_created["json"] = filename

            if export_format in ["txt", "all"]:
                filename = f"imdb_{session_id}_ids.txt"
                save_to_txt_ids(items, os.path.join(OUTPUT_DIR, filename))
                files_created["txt"] = filename

            return render_template("index.html", items=items, files=files_created, url=url, env_lists=ENV_LIST_CACHE)

        except Exception as e:
            logger.exception("Error scraping IMDb list: %s", e)
            flash(f"An error occurred while processing: {str(e)}", "danger")
            return redirect(url_for("index"))
        finally:
            if scraper:
                scraper.close()

    return render_template("index.html", items=None, files=None, env_lists=ENV_LIST_CACHE)


@app.route("/api/lists", methods=["GET"])
def api_get_all_lists():
    return jsonify({
        "status": "success",
        "total_lists": len(ENV_LIST_CACHE),
        "lists": ENV_LIST_CACHE,
    })


@app.route("/api/lists/<list_id>", methods=["GET"])
def api_get_list(list_id):
    if list_id not in ENV_LIST_CACHE:
        return jsonify({"status": "error", "message": f"List '{list_id}' not found."}), 404
    return jsonify({
        "status": "success",
        "list_id": list_id,
        "data": ENV_LIST_CACHE[list_id],
    })


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    if not is_valid_imdb_url(url):
        return jsonify({"status": "error", "message": "Missing or invalid 'url' parameter in request body."}), 400

    scraper = None
    try:
        scraper = IMDbSyncScraper(headless=True)
        items = scraper.fetch_list_items(url)
        return jsonify({
            "status": "success",
            "url": url,
            "total_items": len(items),
            "items": items,
        })
    except Exception as e:
        logger.exception("REST scrape failed: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if scraper:
            scraper.close()


@app.route("/download/<filename>")
def download_file(filename):
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        return "Invalid file name.", 400
    return send_from_directory(OUTPUT_DIR, safe_name, as_attachment=True)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
