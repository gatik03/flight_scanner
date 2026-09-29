import httpx
import pytest
from app.config import Settings
from app.main import create_app
from app.services.health_service import ReadinessService


class HealthDouble:
    def __init__(self, ready: bool) -> None:
        self.ready = ready

    async def check(self) -> bool:
        return self.ready


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret-that-is-at-least-32-characters",
        app_env="test",
    )


@pytest.mark.asyncio
async def test_liveness(settings: Settings) -> None:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_readiness_reports_503_when_dependencies_are_down(settings: Settings) -> None:
    app = create_app(settings)
    app.state.readiness_service = ReadinessService(HealthDouble(False), HealthDouble(False))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"db": "down", "redis": "down"}


@pytest.mark.asyncio
async def test_readiness_reports_200_when_dependencies_are_ready(settings: Settings) -> None:
    app = create_app(settings)
    app.state.readiness_service = ReadinessService(HealthDouble(True), HealthDouble(True))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"db": "ok", "redis": "ok"}}
