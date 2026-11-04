FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    IMDB_USE_SYSTEM_CHROMIUM=1 \
    PORT=4444 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        chromium \
        chromium-driver \
        fonts-liberation \
        xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/.X11-unix \
    && chmod 1777 /tmp/.X11-unix

WORKDIR /app

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint
COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /app/downloaded_files \
    && chmod +x /usr/local/bin/docker-entrypoint \
    && chown -R app:app /app

USER app

EXPOSE 4444

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4444/health', timeout=3)"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint"]

CMD ["gunicorn", "--bind", "0.0.0.0:4444", "--workers", "1", "--threads", "1", "--timeout", "600", "imdb_list_generator.api:app"]
