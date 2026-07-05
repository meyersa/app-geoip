from functools import lru_cache
from pathlib import Path
import tarfile
from typing import Any

import geoip2.database
import geoip2.errors
import httpx
from loguru import logger
import maxminddb

from geoip.config import Settings


class MaxmindLookupError(RuntimeError):
    """Raised when the MaxMind service cannot return usable coordinates."""


async def lookup_ip(
    client: httpx.AsyncClient,
    settings: Settings,
    ip_address: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    db_path = db_path or await ensure_maxmind_database(client, settings)
    logger.debug("Using local MaxMind database at {}", db_path)
    return lookup_ip_from_database(str(db_path), ip_address)


async def ensure_maxmind_database(client: httpx.AsyncClient, settings: Settings) -> Path:
    cache_dir = Path(settings.maxmind_cache_dir)
    current_db = cache_dir / "GeoLite2-City.mmdb"
    if current_db.is_file():
        logger.debug("Found cached MaxMind database at {}", current_db)
        return current_db

    archive_path = cache_dir / "GeoLite2-City.tar.gz"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not archive_path.is_file():
        logger.info("MaxMind database not cached; downloading archive to {}", archive_path)
        await download_maxmind_database(client, settings, archive_path)
    else:
        logger.info("Found cached MaxMind archive at {}; extracting database", archive_path)
    extract_maxmind_database(archive_path, current_db)
    get_database_reader.cache_clear()
    logger.info("Cached MaxMind database at {}", current_db)
    return current_db


async def download_maxmind_database(
    client: httpx.AsyncClient,
    settings: Settings,
    archive_path: Path,
) -> None:
    temporary_path = archive_path.with_suffix(f"{archive_path.suffix}.download")
    logger.info("Downloading MaxMind database archive from {}", settings.maxmind_download_url)
    response = await client.get(
        settings.maxmind_download_url,
        auth=(settings.maxmind_id, settings.maxmind_key),
        follow_redirects=True,
    )
    response.raise_for_status()
    temporary_path.write_bytes(response.content)
    temporary_path.replace(archive_path)
    logger.info("Downloaded MaxMind database archive to {} from {}", archive_path, response.url)


def extract_maxmind_database(archive_path: Path, destination: Path) -> None:
    logger.debug("Extracting MaxMind database from {} to {}", archive_path, destination)
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            member = next((item for item in archive.getmembers() if item.name.endswith(".mmdb") and item.isfile()), None)
            if member is None:
                raise MaxmindLookupError("MaxMind archive did not contain an .mmdb file")
            source = archive.extractfile(member)
            if source is None:
                raise MaxmindLookupError("Could not read .mmdb file from MaxMind archive")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary_destination = destination.with_suffix(f"{destination.suffix}.download")
            with source, temporary_destination.open("wb") as output:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            temporary_destination.replace(destination)
    except (tarfile.TarError, OSError) as exc:
        archive_path.unlink(missing_ok=True)
        logger.error("Failed to extract MaxMind database archive {}: {}", archive_path, exc)
        raise MaxmindLookupError(f"Could not extract MaxMind database archive: {archive_path}") from exc


def lookup_ip_from_database(db_path: str, ip_address: str) -> dict[str, Any]:
    logger.debug("Looking up {} in local MaxMind database", ip_address)
    try:
        response = get_database_reader(db_path).city(ip_address)
    except FileNotFoundError as exc:
        raise MaxmindLookupError(f"MaxMind database not found: {db_path}") from exc
    except PermissionError as exc:
        raise MaxmindLookupError(f"MaxMind database is not readable: {db_path}") from exc
    except maxminddb.InvalidDatabaseError as exc:
        raise MaxmindLookupError(f"Invalid MaxMind database: {db_path}") from exc
    except geoip2.errors.AddressNotFoundError as exc:
        raise MaxmindLookupError(f"IP address was not found in the MaxMind database: {ip_address}") from exc

    data = normalize_geoip_response(response)
    latitude, longitude = extract_coordinates(data)
    data["_geoip"] = {"latitude": latitude, "longitude": longitude}
    logger.debug("Resolved {} to {}, {}", ip_address, latitude, longitude)
    return data


@lru_cache
def get_database_reader(db_path: str) -> geoip2.database.Reader:
    return geoip2.database.Reader(db_path)


def normalize_geoip_response(response: Any) -> dict[str, Any]:
    raw = getattr(response, "raw", None)
    if isinstance(raw, dict):
        return raw

    location = getattr(response, "location", None)
    traits = getattr(response, "traits", None)
    city = getattr(response, "city", None)
    country = getattr(response, "country", None)
    subdivision = getattr(getattr(response, "subdivisions", None), "most_specific", None)

    return {
        "city": record_dict(city, "name", "geoname_id"),
        "country": record_dict(country, "iso_code", "name", "geoname_id"),
        "location": record_dict(location, "latitude", "longitude", "accuracy_radius", "time_zone"),
        "subdivision": record_dict(subdivision, "iso_code", "name", "geoname_id"),
        "traits": record_dict(traits, "ip_address", "network"),
    }


def record_dict(record: Any, *fields: str) -> dict[str, Any]:
    if record is None:
        return {}

    values: dict[str, Any] = {}
    for field in fields:
        value = getattr(record, field, None)
        if value is not None:
            values[field] = str(value) if field == "network" else value
    return values


def extract_coordinates(data: dict[str, Any]) -> tuple[float, float]:
    candidates = (
        data,
        data.get("location"),
        data.get("traits"),
        data.get("geo"),
        data.get("coordinates"),
    )

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        latitude = first_present(candidate, "latitude", "lat")
        longitude = first_present(candidate, "longitude", "lon", "lng")

        if latitude is not None and longitude is not None:
            return validate_coordinates(latitude, longitude)

    raise MaxmindLookupError("MaxMind response did not include latitude and longitude")


def first_present(data: dict[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in data:
            return data[key]
    return None


def validate_coordinates(latitude: Any, longitude: Any) -> tuple[float, float]:
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError) as exc:
        raise MaxmindLookupError("Coordinates must be numeric") from exc

    if not -90 <= lat <= 90:
        raise MaxmindLookupError("Latitude must be between -90 and 90")
    if not -180 <= lon <= 180:
        raise MaxmindLookupError("Longitude must be between -180 and 180")

    return lat, lon
