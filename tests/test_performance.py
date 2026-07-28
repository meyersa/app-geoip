import asyncio
from statistics import median
from time import perf_counter

import httpx

import geoip.app as app_module
from geoip.config import Settings


def test_ip_lookup_latency(monkeypatch) -> None:
    async def lookup_stub(*args, **kwargs) -> dict:
        return {
            "city": {"name": "Detroit"},
            "country": {"name": "United States"},
            "location": {"latitude": 42.3314, "longitude": -83.0458},
            "traits": {"ip_address": "203.0.113.1"},
            "_geoip": {"latitude": 42.3314, "longitude": -83.0458},
        }

    settings = Settings(MAXMIND_ID="test", MAXMIND_KEY="test", LOG_LEVEL="ERROR")
    app_module.app.dependency_overrides[app_module.get_safe_settings] = lambda: settings
    monkeypatch.setattr(app_module, "lookup_ip", lookup_stub)

    async def measure() -> list[float]:
        transport = httpx.ASGITransport(app=app_module.app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/ip/203.0.113.1")
            durations_ms = []
            for _ in range(100):
                started = perf_counter()
                response = await client.get("/ip/203.0.113.1")
                durations_ms.append((perf_counter() - started) * 1_000)
                assert response.status_code == 200
        return durations_ms

    try:
        durations_ms = asyncio.run(measure())
    finally:
        app_module.app.dependency_overrides.clear()

    median_ms = median(durations_ms)
    print(f"IP-only request median: {median_ms:.3f} ms over {len(durations_ms)} requests")
    assert median_ms < 10
