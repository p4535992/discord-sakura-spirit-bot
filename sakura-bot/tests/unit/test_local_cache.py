"""Local TTL cache tests.

Time is driven by an injected clock: no test sleeps, no wall clock is read and
no Redis server is contacted. The cache stores only rebuildable data, so the
"restart" case is simply an empty cache.
"""

import pytest

from core.cache import Cache, get_server_cache, get_user_cache, set_server_cache, set_user_cache


class FakeClock:
    """Deterministic monotonic clock."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def local_cache(clock):
    return Cache(clock=clock)


async def test_set_and_get_round_trip(local_cache):
    await local_cache.set("key", "value")

    assert await local_cache.get("key") == "value"


async def test_connect_never_touches_the_network(local_cache):
    assert local_cache.available is False

    await local_cache.connect()

    assert local_cache.available is True
    assert await local_cache.ping() is True


async def test_entry_expires_after_the_ttl(local_cache, clock):
    await local_cache.set("key", "value", expire=10)

    clock.advance(9)
    assert await local_cache.get("key") == "value"

    clock.advance(1)
    assert await local_cache.get("key") is None
    assert await local_cache.exists("key") is False


async def test_json_reads_are_independent_copies(local_cache):
    payload = {"members": [1]}
    await local_cache.set_json("key", payload)

    payload["members"].append(2)
    assert await local_cache.get_json("key") == {"members": [1]}

    first_read = await local_cache.get_json("key")
    first_read["members"].append(3)
    assert await local_cache.get_json("key") == {"members": [1]}


async def test_delete_and_exists(local_cache):
    await local_cache.set("key", "value")
    assert await local_cache.exists("key") is True

    await local_cache.delete("key")

    assert await local_cache.exists("key") is False
    assert await local_cache.get("key") is None


async def test_increment_keeps_the_expiry(local_cache, clock):
    await local_cache.set("counter", "1", expire=10)

    assert await local_cache.increment("counter") == 2

    clock.advance(10)
    assert await local_cache.get("counter") is None


async def test_increment_starts_from_zero(local_cache):
    assert await local_cache.increment("counter", 5) == 5


async def test_expire_reschedules_and_ignores_missing_keys(local_cache, clock):
    await local_cache.set("key", "value", expire=100)

    await local_cache.expire("key", 5)
    clock.advance(5)
    assert await local_cache.get("key") is None

    # A missing key is a no-op, not an error.
    await local_cache.expire("missing", 5)


async def test_max_entries_is_enforced(clock):
    small = Cache(max_entries=3, clock=clock)

    for index in range(5):
        await small.set(f"key{index}", str(index))

    assert small.size == 3
    assert await small.get("key4") == "4"
    assert await small.get("key0") is None


async def test_disconnect_clears_every_entry(local_cache):
    await local_cache.connect()
    await local_cache.set("key", "value")

    await local_cache.disconnect()

    assert local_cache.available is False
    assert local_cache.size == 0
    assert await local_cache.get("key") is None


async def test_helpers_use_the_documented_keys(local_cache, monkeypatch):
    monkeypatch.setattr("core.cache.cache", local_cache)

    await set_user_cache(42, "profile", {"level": 3})
    await set_server_cache(7, "config", {"language": "it"})

    assert await get_user_cache(42, "profile") == {"level": 3}
    assert await get_server_cache(7, "config") == {"language": "it"}
    assert await local_cache.get("user:42:profile") is not None
    assert await local_cache.get("server:7:config") is not None
