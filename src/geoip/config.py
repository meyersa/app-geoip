from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    maxmind_id: str = Field(alias="MAXMIND_ID")
    maxmind_key: str = Field(alias="MAXMIND_KEY")
    maxmind_download_url: str = Field(
        default="https://download.maxmind.com/geoip/databases/GeoLite2-City/download?suffix=tar.gz",
        alias="MAXMIND_DOWNLOAD_URL",
    )
    maxmind_cache_dir: str = Field(default="/data/GeoIP/maxmind", alias="MAXMIND_CACHE_DIR")
    maxmind_timeout_seconds: float = Field(default=5.0, alias="MAXMIND_TIMEOUT_SECONDS")
    natural_earth_cache_dir: str = Field(default="/data/GeoIP/natural-earth", alias="NATURAL_EARTH_CACHE_DIR")
    natural_earth_countries_url: str = Field(
        default="https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip",
        alias="NATURAL_EARTH_COUNTRIES_URL",
    )
    natural_earth_regions_url: str = Field(
        default="https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_1_states_provinces.zip",
        alias="NATURAL_EARTH_REGIONS_URL",
    )
    natural_earth_lakes_url: str = Field(
        default="https://naturalearth.s3.amazonaws.com/50m_physical/ne_50m_lakes.zip",
        alias="NATURAL_EARTH_LAKES_URL",
    )
    map_image_cache_dir: str = Field(default="/data/GeoIP/maps", alias="MAP_IMAGE_CACHE_DIR")
    map_image_cache_ttl_seconds: int = Field(default=86400, alias="MAP_IMAGE_CACHE_TTL_SECONDS")
    map_zoom_degrees: float = Field(default=12.0, alias="MAP_ZOOM_DEGREES")
    map_width: int = Field(default=1200, alias="MAP_WIDTH")
    map_height: int = Field(default=675, alias="MAP_HEIGHT")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
