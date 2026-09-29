"""Pure protocols used by services to depend on infrastructure capabilities."""

from typing import Protocol


class HealthCheck(Protocol):
    async def check(self) -> bool:
        """Return whether the dependency is ready."""
