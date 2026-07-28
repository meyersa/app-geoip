FROM python:3.14-slim AS deps

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

COPY pyproject.toml poetry.lock ./

RUN poetry install --only main --no-root


FROM deps AS dev

COPY README.md ./
COPY src/ ./src/
COPY tests/ ./tests/

RUN poetry install --with dev

CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "--reload", "geoip.app:app"]


FROM dev AS test

CMD ["geoip-test"]


FROM python:3.14-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=deps /usr/local/ /usr/local/
COPY src/ ./src/

RUN mkdir -p /data/GeoIP/maxmind /data/GeoIP/natural-earth /data/GeoIP/maps

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "geoip.app:app"]
