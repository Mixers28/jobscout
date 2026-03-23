import httpx
import pytest

from app.main import create_app


pytestmark = pytest.mark.anyio


async def _request(path: str) -> httpx.Response:
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)


async def test_root_endpoint_returns_service_metadata() -> None:
    response = await _request("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "jobscout-api"
    assert payload["status"] == "ok"
    assert payload["health"] == "/health"


async def test_favicon_endpoint_returns_no_content() -> None:
    response = await _request("/favicon.ico")
    assert response.status_code == 204


async def test_health_endpoint_returns_ok() -> None:
    response = await _request("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "jobscout-api"


async def test_db_health_endpoint_returns_ok() -> None:
    response = await _request("/health/db")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
