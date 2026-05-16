"""Redis async client setup and cache helper."""

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import settings

_redis_pool: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """Get or create the shared Redis client."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


async def get_redis() -> aioredis.Redis:
    """Async generator yielding a Redis client."""
    redis = await get_redis_client()
    try:
        yield redis
    finally:
        pass


class Cache:
    """Cache helper class for Redis operations."""

    def __init__(self, redis: aioredis.Redis):
        self._redis = redis

    async def get(self, key: str) -> Any:
        """Get a value from cache. Returns None if key does not exist."""
        value = await self._redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
    ) -> None:
        """Set a value in cache with optional TTL (seconds)."""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        await self._redis.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        """Delete a key from cache."""
        await self._redis.delete(key)

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter in Redis. Returns the new value.

        Args:
            key: The counter key.
            amount: Amount to increment by (default 1).

        Returns:
            The new counter value.
        """
        return await self._redis.incr(key, amount)

    async def expire(self, key: str, seconds: int) -> None:
        """Set expiration (TTL) on a key.

        Args:
            key: The key to set TTL on.
            seconds: TTL in seconds.
        """
        await self._redis.expire(key, seconds)

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False


async def get_cache() -> Cache:
    """Get a Cache instance with a connected Redis client."""
    redis = await get_redis_client()
    return Cache(redis)
