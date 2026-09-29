"""Small Redis adapter used by the application boundary."""

from redis.asyncio import Redis
from redis.exceptions import RedisError


class RedisClient:
    """Owns one async Redis client and exposes only required operations."""

    def __init__(self, url: str) -> None:
        self._client: Redis = Redis.from_url(url, decode_responses=True)

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def check(self) -> bool:
        try:
            return await self.ping()
        except RedisError:
            return False

    async def close(self) -> None:
        await self._client.aclose()
