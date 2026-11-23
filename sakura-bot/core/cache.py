"""
Redis cache connection and utilities

The cache is optional at runtime. When Redis is unreachable and
``SAKURA_BOT_CACHE_REQUIRED`` is false, the bot keeps running in degraded mode: every
operation becomes a no-op, the degradation is logged once and the readiness
endpoint reports it. Nothing is hidden and nothing crashes silently.
"""
import json
import logging
from typing import Any, Optional

import redis.asyncio as redis_asyncio
from redis.asyncio import Redis

from core.config import settings

logger = logging.getLogger(__name__)


class Cache:
    """Redis cache manager with an explicit degraded mode."""

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.degraded = False

    async def connect(self):
        """Initialize the Redis connection."""
        try:
            # ``from_url`` is a synchronous factory: awaiting it would raise
            # TypeError because the returned client is not an awaitable.
            self.redis = redis_asyncio.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis.ping()
            self.degraded = False
            logger.info("Redis connection established")
        except Exception:
            self.redis = None
            self.degraded = True
            if settings.cache_required:
                logger.exception("Redis connection failed and SAKURA_BOT_CACHE_REQUIRED is true")
                raise
            logger.warning(
                "Redis connection failed; running in degraded cache mode. "
                "LFG sessions and cooldowns are not persisted."
            )

    async def disconnect(self):
        """Close the Redis connection."""
        if self.redis:
            await self.redis.aclose()
            self.redis = None
            logger.info("Redis connection closed")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if not self.redis:
            return None
        return await self.redis.get(key)
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value from cache."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON from cache key: %s", key)
                return None
        return None
    
    async def set(self, key: str, value: str, expire: Optional[int] = None):
        """Set value in cache with optional expiration (seconds)."""
        if not self.redis:
            return
        await self.redis.set(key, value, ex=expire)
    
    async def set_json(self, key: str, value: Any, expire: Optional[int] = None):
        """Set JSON value in cache."""
        if not self.redis:
            return
        await self.set(key, json.dumps(value), expire)
    
    async def delete(self, key: str):
        """Delete key from cache."""
        if not self.redis:
            return
        await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis:
            return False
        return await self.redis.exists(key) > 0
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        if not self.redis:
            return 0
        return await self.redis.incrby(key, amount)
    
    async def expire(self, key: str, seconds: int):
        """Set expiration on a key."""
        if not self.redis:
            return
        await self.redis.expire(key, seconds)
    
    async def get_hash(self, key: str, field: str) -> Optional[str]:
        """Get hash field value."""
        if not self.redis:
            return None
        return await self.redis.hget(key, field)
    
    async def set_hash(self, key: str, field: str, value: str):
        """Set hash field value."""
        if not self.redis:
            return
        await self.redis.hset(key, field, value)
    
    async def get_all_hash(self, key: str) -> dict:
        """Get all hash fields."""
        if not self.redis:
            return {}
        return await self.redis.hgetall(key)
    
    async def add_to_set(self, key: str, *values: str):
        """Add values to a set."""
        if not self.redis:
            return
        await self.redis.sadd(key, *values)
    
    async def get_set_members(self, key: str) -> set:
        """Get all members of a set."""
        if not self.redis:
            return set()
        return await self.redis.smembers(key)
    
    async def is_set_member(self, key: str, value: str) -> bool:
        """Check if value is in set."""
        if not self.redis:
            return False
        return await self.redis.sismember(key, value)
    
    async def remove_from_set(self, key: str, *values: str):
        """Remove values from a set."""
        if not self.redis:
            return
        await self.redis.srem(key, *values)


# Global cache instance
cache = Cache()


async def init_cache():
    """Initialize Redis connection"""
    await cache.connect()


async def close_cache():
    """Close Redis connection"""
    await cache.disconnect()


# Helper functions for common cache patterns
async def get_user_cache(user_id: int, field: str) -> Optional[Any]:
    """Get cached user data"""
    key = f"user:{user_id}:{field}"
    return await cache.get_json(key)


async def set_user_cache(user_id: int, field: str, value: Any, expire: int = 3600):
    """Set cached user data"""
    key = f"user:{user_id}:{field}"
    await cache.set_json(key, value, expire)


async def get_server_cache(server_id: int, field: str) -> Optional[Any]:
    """Get cached server data"""
    key = f"server:{server_id}:{field}"
    return await cache.get_json(key)


async def set_server_cache(server_id: int, field: str, value: Any, expire: int = 3600):
    """Set cached server data"""
    key = f"server:{server_id}:{field}"
    await cache.set_json(key, value, expire)
