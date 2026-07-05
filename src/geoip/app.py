import asyncio
from contextlib import asynccontextmanager
from ipaddress import ip_address
from pathlib import Path
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path as RoutePath, Request
from fastapi.responses import Response
from loguru import logger
from pydantic import ValidationError

from geoip.config import Settings, get_settings
from geoip.logging import configure_logging
from geoip.maxmind import MaxmindLookupError, ensure_maxmind_database, lookup_ip
from geoip.renderer import ensure_natural_earth, render_map


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_safe_settings()
    app.state.settings = settings
    app.state.maxmind_db_path = None
    app.state.natural_earth_datasets = None

    logger.info("Starting GeoIP")
    logger.info("Preparing startup resources")

    try:
        async with httpx.AsyncClient(timeout=settings.maxmind_timeout_seconds, follow_redirects=True) as client:
            app.state.maxmind_db_path = await ensure_maxmind_database(client, settings)

        app.state.natural_earth_datasets = await asyncio.to_thread(ensure_natural_earth, settings)
    except Exception:
        logger.exception("Startup resource preparation failed")
        raise

    logger.info("Startup resources ready")
    yield
    logger.info("Stopping GeoIP")


app = FastAPI(
    title="GeoIP",
    version="0.1.0",
    description="Look up GeoIP data for an IP address and render its location on a map.",
    lifespan=lifespan,
)


def get_safe_settings() -> Settings:
    try:
        settings = get_settings()
        configure_logging(settings.log_level)
        return settings
    except ValidationError as exc:
        logger.error("Invalid configuration: {}", exc)
        raise HTTPException(status_code=500, detail="Invalid configuration") from exc


@app.get(
    "/{ip}",
    tags=["lookup"],
    summary="Look up GeoIP data",
    description="Returns MaxMind GeoIP data for an IPv4 or IPv6 address.",
)
@app.get(
    "/ip/{ip}",
    tags=["lookup"],
    summary="Look up GeoIP data",
    description="Returns MaxMind GeoIP data for an IPv4 or IPv6 address.",
)
async def ip_info(
    request: Request,
    ip: str = RoutePath(description="IPv4 or IPv6 address to locate"),
    settings: Settings = Depends(get_safe_settings),
) -> dict:
    logger.info("Handling GeoIP lookup request for {}", ip)
    return await get_ip_data(ip, settings, runtime_state(request))


@app.get(
    "/map/{ip}",
    tags=["maps"],
    summary="Render a GeoIP",
    description="Returns a map image with a marker at the MaxMind coordinates for an IPv4 or IPv6 address.",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def map_ip(
    request: Request,
    ip: str = RoutePath(description="IPv4 or IPv6 address to locate"),
    settings: Settings = Depends(get_safe_settings),
) -> Response:
    logger.info("Handling map render request for {}", ip)
    runtime = runtime_state(request)
    data = await get_ip_data(ip, settings, runtime)
    coordinates = data["_geoip"]
    try:
        image = render_map(
            settings,
            data.get("traits", {}).get("ip_address", ip),
            coordinates["latitude"],
            coordinates["longitude"],
            place_name(data),
            runtime.get("natural_earth_datasets"),
        )
    except ValueError as exc:
        logger.error("Map render failed for {}: {}", ip, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    logger.info("Rendered map for {}", ip)
    return Response(content=image, media_type="image/png")


async def get_ip_data(ip: str, settings: Settings, runtime: dict[str, Any] | None = None) -> dict:
    try:
        parsed_ip = ip_address(ip)
    except ValueError as exc:
        logger.warning("Invalid IP address received: {}", ip)
        raise HTTPException(status_code=400, detail="Invalid IP address") from exc

    try:
        async with httpx.AsyncClient(timeout=settings.maxmind_timeout_seconds, follow_redirects=True) as client:
            db_path = runtime.get("maxmind_db_path") if runtime else None
            return await lookup_ip(client, settings, str(parsed_ip), db_path)
    except httpx.HTTPStatusError as exc:
        logger.error("MaxMind lookup failed for {} with HTTP {}", parsed_ip, exc.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"MaxMind service returned HTTP {exc.response.status_code}",
        ) from exc
    except (httpx.HTTPError, MaxmindLookupError, ValueError) as exc:
        logger.error("MaxMind lookup failed for {}: {}", parsed_ip, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def runtime_state(request: Request) -> dict[str, Any]:
    return {
        "maxmind_db_path": getattr(request.app.state, "maxmind_db_path", None),
        "natural_earth_datasets": getattr(request.app.state, "natural_earth_datasets", None),
    }


def place_name(data: dict) -> str:
    city = record_name(data.get("city"))
    country = record_name(data.get("country"))
    return " / ".join(part for part in (city, country) if part)


def record_name(record: object) -> str:
    if not isinstance(record, dict):
        return ""

    name = record.get("name")
    if isinstance(name, str):
        return name

    names = record.get("names")
    if isinstance(names, dict):
        english_name = names.get("en")
        if isinstance(english_name, str):
            return english_name

    return ""
