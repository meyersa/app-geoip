from io import BytesIO
from pathlib import Path
import zipfile
from math import cos, radians
from urllib.request import urlopen

from loguru import logger
from PIL import Image, ImageDraw, ImageFont
import shapefile

from geoip.config import Settings


WEB_MERCATOR_LATITUDE_LIMIT = 85.0511
COLOR_LAND = "#7E8987"
COLOR_WATER = "#FFFFFF"
COLOR_ICON = "#D1495B"
COLOR_TEXT = "#0A0A0A"
COLOR_BOUNDARY = "#F4F5F5"


def render_map(
    settings: Settings,
    ip_address: str,
    latitude: float,
    longitude: float,
    place_name: str,
    datasets: dict[str, Path] | None = None,
) -> bytes:
    width = clamp(settings.map_width, 1, 1280)
    height = clamp(settings.map_height, 1, 1280)
    viewport = viewport_for(longitude, latitude, settings.map_zoom_degrees, width, height)
    logger.debug("Rendering map for {} at {}, {} with viewport {}", ip_address, latitude, longitude, viewport)
    datasets = datasets or ensure_natural_earth(settings)

    image = Image.new("RGB", (width, height), COLOR_WATER)
    draw = ImageDraw.Draw(image)

    draw_graticule(draw, viewport, width, height)
    draw_shapefile(draw, datasets["countries"], viewport, width, height, fill=COLOR_LAND, outline=COLOR_BOUNDARY, width_px=1)
    draw_shapefile(draw, datasets["lakes"], viewport, width, height, fill=COLOR_WATER, outline=COLOR_BOUNDARY, width_px=1)
    draw_shapefile(draw, datasets["regions"], viewport, width, height, fill=None, outline=COLOR_BOUNDARY, width_px=1)
    marker_x, marker_y = project(longitude, latitude, viewport, width, height)
    draw_pin(draw, marker_x, marker_y)
    draw_label(draw, ip_address, latitude, longitude, place_name, height)

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    logger.debug("Rendered {} byte PNG map for {}", len(buffer.getvalue()), ip_address)
    return buffer.getvalue()


def ensure_natural_earth(settings: Settings) -> dict[str, Path]:
    cache_dir = Path(settings.natural_earth_cache_dir)
    logger.debug("Using Natural Earth cache at {}", cache_dir)
    return {
        "countries": ensure_shapefile(cache_dir, settings.natural_earth_countries_url),
        "regions": ensure_shapefile(cache_dir, settings.natural_earth_regions_url),
        "lakes": ensure_shapefile(cache_dir, settings.natural_earth_lakes_url),
    }


def ensure_shapefile(cache_dir: Path, url: str) -> Path:
    dataset_name = Path(url).stem
    dataset_dir = cache_dir / dataset_name
    shapefile_path = dataset_dir / f"{dataset_name}.shp"
    if shapefile_path.is_file():
        logger.debug("Found cached Natural Earth shapefile at {}", shapefile_path)
        return shapefile_path

    dataset_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dataset_dir / f"{dataset_name}.zip"
    if not archive_path.is_file():
        logger.info("Natural Earth shapefile {} not cached; downloading", dataset_name)
        download_file(url, archive_path)
    else:
        logger.info("Found cached Natural Earth archive at {}; extracting", archive_path)

    try:
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(dataset_dir)
    except zipfile.BadZipFile as exc:
        archive_path.unlink(missing_ok=True)
        logger.error("Invalid Natural Earth zip archive from {}", url)
        raise ValueError(f"Natural Earth archive is not a valid zip file: {url}") from exc

    if not shapefile_path.is_file():
        logger.error("Natural Earth archive did not contain expected shapefile {}", shapefile_path.name)
        raise ValueError(f"Natural Earth archive did not contain {shapefile_path.name}")
    logger.info("Cached Natural Earth shapefile at {}", shapefile_path)
    return shapefile_path


def download_file(url: str, destination: Path) -> None:
    temporary = destination.with_suffix(f"{destination.suffix}.download")
    try:
        logger.info("Downloading map data from {}", url)
        with urlopen(url, timeout=120) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        temporary.replace(destination)
        logger.info("Downloaded map data to {}", destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        logger.error("Could not download map data from {}: {}", url, exc)
        raise ValueError(f"Could not download map data from {url}") from exc


def viewport_for(longitude: float, latitude: float, span_degrees: float, width: int, height: int) -> tuple[float, float, float, float]:
    lat_span = max(1.0, min(span_degrees, 160.0))
    lon_span = lat_span * width / height / max(0.25, cos(radians(latitude)))
    lon_span = max(1.0, min(lon_span, 360.0))
    min_lon = max(-180.0, longitude - lon_span / 2)
    max_lon = min(180.0, longitude + lon_span / 2)
    min_lat = max(-WEB_MERCATOR_LATITUDE_LIMIT, latitude - lat_span / 2)
    max_lat = min(WEB_MERCATOR_LATITUDE_LIMIT, latitude + lat_span / 2)
    return min_lon, min_lat, max_lon, max_lat


def draw_shapefile(
    draw: ImageDraw.ImageDraw,
    path: Path,
    viewport: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    fill: str | None,
    outline: str,
    width_px: int,
) -> None:
    reader = shapefile.Reader(str(path))
    for shape in reader.iterShapes():
        if not intersects(shape.bbox, viewport):
            continue
        points = shape.points
        part_starts = list(shape.parts) + [len(points)]
        for start, end in zip(part_starts, part_starts[1:]):
            projected = [
                project(lon, lat, viewport, image_width, image_height)
                for lon, lat in points[start:end]
            ]
            if len(projected) < 2:
                continue
            if fill and len(projected) >= 3:
                draw.polygon(projected, fill=fill, outline=outline)
            else:
                draw.line(projected, fill=outline, width=width_px, joint="curve")


def intersects(bbox: list[float], viewport: tuple[float, float, float, float]) -> bool:
    min_lon, min_lat, max_lon, max_lat = viewport
    return not (bbox[2] < min_lon or bbox[0] > max_lon or bbox[3] < min_lat or bbox[1] > max_lat)


def project(lon: float, lat: float, viewport: tuple[float, float, float, float], width: int, height: int) -> tuple[int, int]:
    min_lon, min_lat, max_lon, max_lat = viewport
    x = int(round((lon - min_lon) / (max_lon - min_lon) * width))
    y = int(round((max_lat - lat) / (max_lat - min_lat) * height))
    return x, y


def draw_graticule(draw: ImageDraw.ImageDraw, viewport: tuple[float, float, float, float], width: int, height: int) -> None:
    min_lon, min_lat, max_lon, max_lat = viewport
    step = graticule_step(max(max_lon - min_lon, max_lat - min_lat))
    lon = round_down(min_lon, step)
    while lon <= max_lon:
        x, _ = project(lon, min_lat, viewport, width, height)
        draw.line((x, 0, x, height), fill="#9fb8b6", width=1)
        lon += step

    lat = round_down(min_lat, step)
    while lat <= max_lat:
        _, y = project(min_lon, lat, viewport, width, height)
        draw.line((0, y, width, y), fill="#9fb8b6", width=1)
        lat += step


def graticule_step(span: float) -> float:
    if span <= 5:
        return 1
    if span <= 15:
        return 2
    if span <= 45:
        return 5
    return 10


def round_down(value: float, step: float) -> float:
    return value - (value % step)


def draw_pin(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    halo = 28
    radius = 13
    draw.ellipse((x - halo, y - halo, x + halo, y + halo), fill="#ebb1b9")
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=COLOR_ICON, outline="#7b1f2c", width=3)
    draw.polygon([(x - 8, y + 10), (x + 8, y + 10), (x, y + 34)], fill=COLOR_ICON, outline="#7b1f2c")


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def draw_label(
    draw: ImageDraw.ImageDraw,
    ip_address: str,
    latitude: float,
    longitude: float,
    place_name: str,
    image_height: int,
) -> None:
    title = f"{ip_address}"
    subtitle = f"{longitude:.4f}, {latitude:.4f}"
    place = place_name or "Unknown location"

    title_font = font(68, bold=True)
    subtitle_font = font(40)
    place_font = font(52)
    label_height = 240
    x = 24
    y = image_height - label_height - 24

    draw.text((x, y + 12), title, fill=COLOR_ICON, font=title_font)
    draw.text((x, y + 94), subtitle, fill=COLOR_TEXT, font=subtitle_font)
    draw.text((x, y + 148), place, fill=COLOR_TEXT, font=place_font)


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = ("Arial Bold.ttf", "Arial.ttf") if bold else ("Arial.ttf",)
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
