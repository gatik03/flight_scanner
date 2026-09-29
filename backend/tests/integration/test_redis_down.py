import httpx
import pytest
from app.config import Settings
from app.infra.cache.redis_client import RedisClient
from app.main import create_app
from app.services.health_service import ReadinessService


class HealthyDatabase:
    async def check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_readiness_returns_503_when_redis_is_stopped() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        redis_url="unix:///tmp/flight-scanner-stopped-redis.sock?db=0",
        jwt_secret="test-secret-that-is-at-least-32-characters",
        app_env="test",
    )
    app = create_app(settings)
    redis = RedisClient(settings.redis_url)
    app.state.redis = redis
    app.state.readiness_service = ReadinessService(HealthyDatabase(), redis)
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")
    finally:
        await redis.close()

    assert response.status_code == 503
    assert response.json()["checks"] == {"db": "ok", "redis": "down"}
