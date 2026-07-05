# AGENTS.md

## Project

GeoIP is a FastAPI service that returns MaxMind GeoIP JSON and renders a PNG map for an IP address.

The Python package lives in `src/geoip`. Tests live in `tests`.

## Commands

Install dependencies:

```bash
poetry install
```

Run the app locally:

```bash
poetry run granian --interface asgi --reload geoip.app:app
```

Run via the package script:

```bash
poetry run GeoIP
```

Run tests:

```bash
poetry run geoip-test
```

The test command wraps `pytest -q`.

## Runtime Notes

The app prepares external data during FastAPI startup:

- MaxMind GeoLite2 City database with `MAXMIND_ID` and `MAXMIND_KEY`.
- Natural Earth countries, admin-1 regions, and lakes shapefiles.

Default persistent cache paths are under `/data/GeoIP`:

- `MAXMIND_CACHE_DIR=/data/GeoIP/maxmind`
- `NATURAL_EARTH_CACHE_DIR=/data/GeoIP/natural-earth`

For local tests, `.env` may point these caches at `/tmp`.

## API

- `GET /{ip}` returns GeoIP JSON.
- `GET /ip/{ip}` returns GeoIP JSON.
- `GET /map/{ip}` returns a PNG map.
- `GET /docs` exposes FastAPI docs.
- `GET /openapi.json` exposes the OpenAPI spec.

## Docker

The Dockerfile installs from `poetry.lock` and runs Granian:

```bash
granian --interface asgi --host 0.0.0.0 --port 8000 geoip.app:app
```

Mount `/data/GeoIP` as a volume when you want downloaded MaxMind and Natural Earth data to persist across restarts.

## Safety

Do not print or commit `.env` values. `MAXMIND_ID` and `MAXMIND_KEY` are secrets.

Do not log credential values. Existing logging should mention cache paths, modes, and URLs, but not the MaxMind key.

Keep generated cache data out of the repo. Natural Earth and MaxMind data should stay in configured cache directories.
