"""Readiness use case."""

from dataclasses import dataclass

from app.domain.ports import HealthCheck


@dataclass(frozen=True)
class ReadinessResult:
    database: bool
    redis: bool

    @property
    def ready(self) -> bool:
        return self.database and self.redis


class ReadinessService:
    """Orchestrate dependency checks without knowing their implementations."""

    def __init__(self, database: HealthCheck, redis: HealthCheck) -> None:
        self._database = database
        self._redis = redis

    async def check(self) -> ReadinessResult:
        return ReadinessResult(
            database=await self._database.check(),
            redis=await self._redis.check(),
        )
