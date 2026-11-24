"""
In-process TTL cache.

The bot serves one or two small guilds from a single process, so a local cache
replaces the former Redis instance: no extra container, no network hop, no
service to keep alive. It is **not** shared between processes or replicas:
never start two bot replicas that rely on this cache for coordination.

Only rebuildable read-through data belongs here (user profile, currency, server
config): every value can be recomputed from PostgreSQL. Game state that must
survive a restart (LFG sessions, ritual cooldowns) lives in PostgreSQL, see
``core.lfg_repository``.

Expiry uses ``time.monotonic()``, so a wall-clock jump cannot resurrect or
expire an entry early. Values are stored serialised, exactly like the former
Redis client did, which makes ``get_json`` return an independent copy instead of
a mutable reference to the internal state.
"""
import asyncio
import json
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Upper bound: the cache must not grow with the number of users seen since boot.
DEFAULT_MAX_ENTRIES = 2048


class Cache:
    """Async TTL cache backed by a dict guarded by an ``asyncio.Lock``."""

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ):
        # ``clock`` is injectable so the tests can move time without sleeping.
        self._max_entries = max_entries
        self._clock = clock
        # key -> (deadline on the injected clock, serialised value)
        self._entries: dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()
        self._available = False

    @property
    def available(self) -> bool:
        """True once ``connect()`` ran; ``ping()`` reports it to the probe."""
        return self._available

    @property
    def size(self) -> int:
        """Number of stored entries, expired ones included until the next access."""
        return len(self._entries)

    async def connect(self):
        """Initialise the cache. It is local: no socket, no retry, no network."""
        async with self._lock:
            self._entries.clear()
        self._available = True
        logger.info("Local TTL cache initialised (max %s entries)", self._max_entries)

    async def disconnect(self):
        """Drop every entry; a restart starts empty by design."""
        async with self._lock:
            self._entries.clear()
        self._available = False
        logger.info("Local TTL cache cleared")

    async def ping(self, timeout: float = 5.0) -> bool:
        """Readiness check of the local cache: never touches the network.

        ``timeout`` is accepted for signature compatibility with the former
        Redis client and is unused.
        """
        return self._available

    def _deadline(self, expire: Optional[int]) -> float:
        if expire is None:
            return float("inf")
        return self._clock() + expire

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, (deadline, _) in self._entries.items() if deadline <= now]
        for key in expired:
            del self._entries[key]

    def _evict_one(self) -> None:
        """Drop the entry that would expire first, or the oldest one."""
        victim = min(self._entries, key=lambda key: self._entries[key][0])
        del self._entries[victim]
    
    async def get(self, key: str) -> Optional[str]:
        """Return the stored string, or ``None`` when missing or expired."""
        async with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is None:
                return None
            deadline, value = entry
            if deadline <= now:
                del self._entries[key]
                return None
            return value
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Return a decoded copy of the stored JSON value."""
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from cache key: %s", key)
            return None
    
    async def set(self, key: str, value: str, expire: Optional[int] = None):
        """Store ``value`` for ``expire`` seconds (no expiry when omitted)."""
        async with self._lock:
            now = self._clock()
            self._purge_expired(now)
            if key not in self._entries and len(self._entries) >= self._max_entries:
                self._evict_one()
            self._entries[key] = (self._deadline(expire), value)
    
    async def set_json(self, key: str, value: Any, expire: Optional[int] = None):
        """Store ``value`` serialised, so later reads cannot mutate it."""
        await self.set(key, json.dumps(value), expire)
    
    async def delete(self, key: str):
        """Remove ``key`` if present."""
        async with self._lock:
            self._entries.pop(key, None)
    
    async def exists(self, key: str) -> bool:
        """True when ``key`` is present and not expired."""
        return await self.get(key) is not None
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Add ``amount`` to a counter, keeping the existing expiry."""
        async with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            current = 0
            deadline = float("inf")
            if entry is not None:
                entry_deadline, raw = entry
                if entry_deadline > now:
                    deadline = entry_deadline
                    try:
                        current = int(raw)
                    except (TypeError, ValueError):
                        current = 0
            new_value = current + amount
            if key not in self._entries and len(self._entries) >= self._max_entries:
                self._evict_one()
            self._entries[key] = (deadline, str(new_value))
            return new_value
    
    async def expire(self, key: str, seconds: int):
        """Set a new expiry on an existing key; a missing key is a no-op."""
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return
            self._entries[key] = (self._deadline(seconds), entry[1])
    
    async def clear(self):
        """Remove every entry without changing the availability flag."""
        async with self._lock:
            self._entries.clear()


# Global cache instance
cache = Cache()


async def init_cache():
    """Initialise the in-process cache"""
    await cache.connect()


async def close_cache():
    """Clear the in-process cache"""
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
