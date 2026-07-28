from ipaddress import ip_address

from geoip.app import app, place_name


def test_openapi_documents_public_routes() -> None:
    schema = app.openapi()

    assert set(schema["paths"]) == {"/{ip}", "/ip/{ip}", "/map/{ip}"}
    assert "200" in schema["paths"]["/{ip}"]["get"]["responses"]
    assert "200" in schema["paths"]["/ip/{ip}"]["get"]["responses"]
    assert "image/png" in schema["paths"]["/map/{ip}"]["get"]["responses"]["200"]["content"]


def test_place_name_prefers_city_and_country() -> None:
    assert place_name({"city": {"name": "Detroit"}, "country": {"names": {"en": "United States"}}}) == "Detroit / United States"


def test_map_image_cache_roundtrip(tmp_path) -> None:
    from geoip.config import Settings
    from geoip.image_cache import cache_key, map_cache_payload, read_cached_image, write_cached_image

    settings = Settings(
        MAXMIND_ID="account",
        MAXMIND_KEY="license",
        MAP_IMAGE_CACHE_DIR=str(tmp_path),
        MAP_IMAGE_CACHE_TTL_SECONDS=86400,
    )
    key = cache_key(map_cache_payload(settings, "203.0.113.1", 42.3314, -83.0458, "Detroit / United States"))

    assert read_cached_image(settings, key) is None

    write_cached_image(settings, key, b"png")

    assert read_cached_image(settings, key) == b"png"


def test_map_cache_payload_serializes_ip_address_objects(tmp_path) -> None:
    from geoip.config import Settings
    from geoip.image_cache import cache_key, map_cache_payload

    settings = Settings(
        MAXMIND_ID="account",
        MAXMIND_KEY="license",
        MAP_IMAGE_CACHE_DIR=str(tmp_path),
    )
    payload = map_cache_payload(
        settings,
        ip_address("203.0.113.1"),
        42.3314,
        -83.0458,
        "Detroit / United States",
    )

    assert payload["ip"] == "203.0.113.1"
    assert cache_key(payload)
