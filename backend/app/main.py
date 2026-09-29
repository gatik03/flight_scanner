"""FastAPI application factory and lifespan."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.errors import app_error_handler, unhandled_error_handler, validation_error_handler
from app.api.middleware import RequestIdMiddleware, configure_logging
from app.api.routes.health import router as health_router
from app.config import Settings, get_settings
from app.domain.errors import AppError
from app.infra.cache.redis_client import RedisClient
from app.infra.db.health import DatabaseHealth
from app.infra.db.session import create_engine
from app.services.health_service import ReadinessService


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)
    engine = create_engine(runtime_settings.database_url)
    redis = RedisClient(runtime_settings.redis_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await redis.close()
        await engine.dispose()

    app = FastAPI(title="Flight Deal Aggregator", lifespan=lifespan)
    app.state.engine = engine
    app.state.redis = redis
    app.state.readiness_service = ReadinessService(DatabaseHealth(engine), redis)
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(health_router)
    return app


app = create_app()
