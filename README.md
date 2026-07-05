# GeoIP

Returns MaxMind GeoIP data for an IP address and generates a PNG map from its coordinates.

## Run

```bash
poetry install
poetry run granian --interface asgi --reload geoip.app:app
```

You can also use the project script, which runs Granian on `0.0.0.0:8000`:

```bash
poetry run GeoIP
```

## Test

```bash
poetry run geoip-test
```

This wraps:

```bash
poetry run pytest -q
```

## Docker

```bash
docker build -t GeoIP .
docker run --rm -p 8000:8000 \
  -e MAXMIND_ID=your_account_id \
  -e MAXMIND_KEY=your_license_key \
  -v GeoIP-data:/data/GeoIP \
  GeoIP
```

The image installs dependencies from `poetry.lock` and runs Granian:

```bash
granian --interface asgi --host 0.0.0.0 --port 8000 geoip.app:app
```

## API

| Route       | Response | Description                                             |
| ----------- | -------- | ------------------------------------------------------- |
| `/{ip}`     | JSON     | Returns MaxMind GeoIP data for an IP address.           |
| `/ip/{ip}`  | JSON     | Alias for `/{ip}`.                                      |
| `/map/{ip}` | Image    | Returns a map with a marker at the MaxMind coordinates. |

Examples:

```text
http://127.0.0.1:8000/1.1.1.1
http://127.0.0.1:8000/ip/1.1.1.1
http://127.0.0.1:8000/map/1.1.1.1
```

FastAPI also exposes generated API docs:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

Map rendering uses Natural Earth vector data. On startup, the app checks/downloads countries, states/provinces, and lakes into a local cache. No hosted map API, token, or pre-bundled map file is required.

## Environment

| Name                        | Value                                                                               | Required |
| --------------------------- | ----------------------------------------------------------------------------------- | -------- |
| MAXMIND_ID                  | MaxMind account ID for downloading GeoLite2 City                                    | Yes      |
| MAXMIND_KEY                 | MaxMind license key for downloading GeoLite2 City                                   | Yes      |
| MAXMIND_DOWNLOAD_URL        | GeoLite2 City tarball URL; defaults to MaxMind's `GeoLite2-City` download endpoint  | No       |
| MAXMIND_CACHE_DIR           | Download/extract cache; defaults to `/data/GeoIP/maxmind`                       | No       |
| MAXMIND_TIMEOUT_SECONDS     | Float: `5.0`                                                                        | No       |
| LOG_LEVEL                   | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`; defaults to `INFO`              | No       |
| NATURAL_EARTH_CACHE_DIR     | Download/extract cache; defaults to `/data/GeoIP/natural-earth`                 | No       |
| NATURAL_EARTH_COUNTRIES_URL | Countries shapefile zip URL; defaults to Natural Earth 1:50m countries              | No       |
| NATURAL_EARTH_REGIONS_URL   | States/provinces shapefile zip URL; defaults to Natural Earth 1:50m admin-1 regions | No       |
| NATURAL_EARTH_LAKES_URL     | Lakes shapefile zip URL; defaults to Natural Earth 1:50m lakes                      | No       |
| MAP_ZOOM_DEGREES            | Approximate latitude span around the point; defaults to `12.0`                      | No       |
| MAP_WIDTH                   | Integer from `1` to `1280`; defaults to `1200`                                      | No       |
| MAP_HEIGHT                  | Integer from `1` to `1280`; defaults to `675`                                       | No       |

By default, the app downloads MaxMind's GeoLite2 City database with HTTP basic auth and caches the extracted `.mmdb` file. On startup, it checks the cache before downloading anything:

```env
MAXMIND_ID=your_account_id
MAXMIND_KEY=your_license_key
MAXMIND_CACHE_DIR=/data/GeoIP/maxmind
NATURAL_EARTH_CACHE_DIR=/data/GeoIP/natural-earth
MAP_ZOOM_DEGREES=12
LOG_LEVEL=INFO
```

For Docker, mount `/data/GeoIP` as a volume if you want MaxMind and Natural Earth downloads to persist across container restarts.

For local testing, point the caches at `/tmp`:

```env
MAXMIND_CACHE_DIR=/tmp/GeoIP/maxmind
NATURAL_EARTH_CACHE_DIR=/tmp/GeoIP/natural-earth
```

The default Natural Earth downloads are small public-domain shapefiles: countries, internal administrative divisions, and lakes. They are detailed enough to show the part of the world and state/province-level context without bundling street maps.
