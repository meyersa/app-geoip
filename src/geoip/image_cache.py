from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Any

from loguru import logger

from geoip.config import Settings


CACHE_VERSION = 3


def cache_key(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def map_cache_payload(
    settings: Settings,
    ip_address: object,
    latitude: float,
    longitude: float,
    place_name: str,
) -> dict[str, Any]:
    return {
        "version": CACHE_VERSION,
        "ip": str(ip_address),
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        "place": place_name,
        "width": settings.map_width,
        "height": settings.map_height,
        "zoom_degrees": settings.map_zoom_degrees,
    }


def cache_path(settings: Settings, key: str) -> Path:
    return Path(settings.map_image_cache_dir) / f"{key}.png"


def read_cached_image(settings: Settings, key: str) -> bytes | None:
    if settings.map_image_cache_ttl_seconds <= 0:
        logger.debug("Map image cache disabled")
        return None

    path = cache_path(settings, key)
    if not path.is_file():
        logger.debug("Map image cache miss for {}", key)
        return None

    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > settings.map_image_cache_ttl_seconds:
        logger.info("Map image cache entry expired for {}", key)
        return None

    logger.info("Map image cache hit for {}", key)
    return path.read_bytes()


def write_cached_image(settings: Settings, key: str, image: bytes) -> None:
    if settings.map_image_cache_ttl_seconds <= 0:
        return

    path = cache_path(settings, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".png.download")
    temporary_path.write_bytes(image)
    temporary_path.replace(path)
    logger.info("Cached map image at {}", path)
