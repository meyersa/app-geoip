import asyncio
from pathlib import Path
import tarfile

import httpx
import pytest

from geoip.config import Settings
from geoip.maxmind import MaxmindLookupError, ensure_maxmind_database, extract_coordinates, extract_maxmind_database, lookup_ip, record_dict
from geoip.maxmind import download_maxmind_database
from geoip.renderer import clamp, graticule_step, viewport_for


def test_extract_coordinates_from_maxmind_location() -> None:
    assert extract_coordinates({"location": {"latitude": 42.3314, "longitude": -83.0458}}) == (
        42.3314,
        -83.0458,
    )


def test_extract_coordinates_from_flat_response() -> None:
    assert extract_coordinates({"lat": "37.7749", "lon": "-122.4194"}) == (37.7749, -122.4194)


def test_extract_coordinates_rejects_invalid_latitude() -> None:
    with pytest.raises(MaxmindLookupError):
        extract_coordinates({"latitude": 100, "longitude": 0})


def test_record_dict_stringifies_network() -> None:
    class Record:
        network = "203.0.113.0/24"

    assert record_dict(Record(), "network") == {"network": "203.0.113.0/24"}


def test_extract_maxmind_database_finds_mmdb(tmp_path: Path) -> None:
    source = tmp_path / "GeoLite2-City_20260704" / "GeoLite2-City.mmdb"
    source.parent.mkdir()
    source.write_bytes(b"mmdb")
    archive_path = tmp_path / "GeoLite2-City.tar.gz"
    destination = tmp_path / "cache" / "GeoLite2-City.mmdb"

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source, arcname="GeoLite2-City_20260704/GeoLite2-City.mmdb")

    extract_maxmind_database(archive_path, destination)

    assert destination.read_bytes() == b"mmdb"


def test_extract_maxmind_database_rejects_archive_without_mmdb(tmp_path: Path) -> None:
    source = tmp_path / "README.txt"
    source.write_text("not a database")
    archive_path = tmp_path / "GeoLite2-City.tar.gz"

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source, arcname="README.txt")

    with pytest.raises(MaxmindLookupError, match="did not contain"):
        extract_maxmind_database(archive_path, tmp_path / "GeoLite2-City.mmdb")


def test_download_maxmind_database_uses_basic_auth(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(200, content=b"archive")

    settings = Settings(
        MAXMIND_ID="account",
        MAXMIND_KEY="license",
        MAXMIND_DOWNLOAD_URL="https://download.maxmind.test/GeoLite2-City.tar.gz",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    archive_path = tmp_path / "GeoLite2-City.tar.gz"

    try:
        asyncio.run(download_maxmind_database(client, settings, archive_path))
    finally:
        asyncio.run(client.aclose())

    assert archive_path.read_bytes() == b"archive"


def test_download_maxmind_database_follows_redirect(tmp_path: Path) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url) == "https://download.maxmind.test/GeoLite2-City.tar.gz":
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(302, headers={"location": "https://r2.example.test/GeoLite2-City.tar.gz"})
        return httpx.Response(200, content=b"redirected-archive")

    settings = Settings(
        MAXMIND_ID="account",
        MAXMIND_KEY="license",
        MAXMIND_DOWNLOAD_URL="https://download.maxmind.test/GeoLite2-City.tar.gz",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    archive_path = tmp_path / "GeoLite2-City.tar.gz"

    try:
        asyncio.run(download_maxmind_database(client, settings, archive_path))
    finally:
        asyncio.run(client.aclose())

    assert seen_urls == [
        "https://download.maxmind.test/GeoLite2-City.tar.gz",
        "https://r2.example.test/GeoLite2-City.tar.gz",
    ]
    assert archive_path.read_bytes() == b"redirected-archive"


def test_ensure_maxmind_database_extracts_cached_archive_without_download(tmp_path: Path) -> None:
    source = tmp_path / "GeoLite2-City_20260704" / "GeoLite2-City.mmdb"
    source.parent.mkdir()
    source.write_bytes(b"mmdb")
    cache_dir = tmp_path / "cache"
    archive_path = cache_dir / "GeoLite2-City.tar.gz"
    archive_path.parent.mkdir()

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source, arcname="GeoLite2-City_20260704/GeoLite2-City.mmdb")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("download should not be called when the archive is cached")

    settings = Settings(MAXMIND_ID="account", MAXMIND_KEY="license", MAXMIND_CACHE_DIR=str(cache_dir))
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    try:
        db_path = asyncio.run(ensure_maxmind_database(client, settings))
    finally:
        asyncio.run(client.aclose())

    assert db_path == cache_dir / "GeoLite2-City.mmdb"
    assert db_path.read_bytes() == b"mmdb"


def test_clamp() -> None:
    assert clamp(1500, 1, 1280) == 1280


def test_viewport_contains_center() -> None:
    longitude, latitude = -83.0458, 42.3314
    min_lon, min_lat, max_lon, max_lat = viewport_for(longitude, latitude, 12, 1200, 675)

    assert min_lon < longitude < max_lon
    assert min_lat < latitude < max_lat


def test_graticule_step() -> None:
    assert graticule_step(4) == 1
    assert graticule_step(12) == 2
    assert graticule_step(40) == 5
    assert graticule_step(100) == 10
