"""Liveness and dependency readiness endpoints."""

from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.services.health_service import ReadinessService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: process is running; no dependency check is performed."""

    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request, response: Response) -> dict[str, Any]:
    """Readiness: both required infrastructure dependencies answer successfully."""

    result: ReadinessService = request.app.state.readiness_service
    readiness_result = await result.check()
    checks = {
        "db": "ok" if readiness_result.database else "down",
        "redis": "ok" if readiness_result.redis else "down",
    }
    if readiness_result.ready:
        return {"status": "ok", "checks": checks}

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not_ready", "checks": checks}
