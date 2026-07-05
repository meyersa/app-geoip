FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.4.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential tini \
    && pip install --no-cache-dir "poetry==${POETRY_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock README.md ./
COPY src/ ./src/

RUN poetry install --only main

RUN mkdir -p /data/GeoIP/maxmind /data/GeoIP/natural-earth

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "geoip.app:app"]
