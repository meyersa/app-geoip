from geoip.app import app, place_name


def test_openapi_documents_public_routes() -> None:
    schema = app.openapi()

    assert set(schema["paths"]) == {"/{ip}", "/ip/{ip}", "/map/{ip}"}
    assert "200" in schema["paths"]["/{ip}"]["get"]["responses"]
    assert "200" in schema["paths"]["/ip/{ip}"]["get"]["responses"]
    assert "image/png" in schema["paths"]["/map/{ip}"]["get"]["responses"]["200"]["content"]


def test_place_name_prefers_city_and_country() -> None:
    assert place_name({"city": {"name": "Detroit"}, "country": {"names": {"en": "United States"}}}) == "Detroit / United States"
