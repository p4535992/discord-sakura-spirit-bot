"""Liveness and readiness probe tests.

The probes are driven with fakes: no Discord connection, no database and no
remote cache is contacted. ``aiohttp.test_utils`` binds an ephemeral loopback
port, so the tests stay offline.
"""

import pytest
from aiohttp.test_utils import TestClient, TestServer

import core.health as health_module
from core.health import HealthServer


class FakeBot:
    """Minimal stand-in for ``discord.Client``: only ``is_ready`` is used."""

    def __init__(self, ready: bool):
        self._ready = ready

    def is_ready(self) -> bool:
        return self._ready


class FakeDatabase:
    """Stand-in for ``core.database.db``."""

    def __init__(self, ready: bool):
        self._ready = ready

    async def ping(self, timeout: float = 5.0) -> bool:
        return self._ready


class FakeCache:
    """Stand-in for ``core.cache.cache``."""

    def __init__(self, ready: bool):
        self._ready = ready

    async def ping(self, timeout: float = 5.0) -> bool:
        return self._ready


@pytest.fixture
async def make_probe(monkeypatch):
    """Return a factory producing a started client plus its HealthServer."""
    clients: list[TestClient] = []

    async def _make(
        *,
        bot_ready: bool = True,
        database_ready: bool = True,
        cache_ready: bool = True,
        bootstrap_complete: bool = True,
        startup_failures: list[str] | None = None,
    ):
        monkeypatch.setattr(health_module, "db", FakeDatabase(database_ready))
        monkeypatch.setattr(health_module, "cache", FakeCache(cache_ready))

        server = HealthServer()
        server.attach(FakeBot(bot_ready))
        server.bootstrap_complete = bootstrap_complete
        server.startup_failures = list(startup_failures or [])

        client = TestClient(TestServer(server.create_app()))
        await client.start_server()
        clients.append(client)
        return client, server

    yield _make

    for client in clients:
        await client.close()


async def test_health_reports_liveness_before_the_gateway_is_connected(make_probe):
    client, _ = await make_probe(bot_ready=False, bootstrap_complete=False)

    response = await client.get("/health")

    assert response.status == 200
    assert await response.json() == {"status": "ok"}


async def test_ready_is_503_before_the_gateway_is_connected(make_probe):
    client, _ = await make_probe(bot_ready=False)

    response = await client.get("/ready")
    payload = await response.json()

    assert response.status == 503
    assert payload["status"] == "not_ready"
    assert payload["checks"]["discord"] is False


async def test_ready_is_200_when_everything_is_available(make_probe):
    client, _ = await make_probe()

    response = await client.get("/ready")
    payload = await response.json()

    assert response.status == 200
    assert payload["status"] == "ready"
    assert payload["checks"] == {
        "discord": True,
        "bootstrap": True,
        "database": True,
        "cache": True,
        "extensions": True,
    }


async def test_ready_is_503_when_the_database_is_down(make_probe):
    client, _ = await make_probe(database_ready=False)

    response = await client.get("/ready")
    payload = await response.json()

    assert response.status == 503
    assert payload["checks"]["database"] is False


async def test_ready_is_503_when_the_local_cache_is_not_initialised(make_probe):
    """The in-process cache is part of the bootstrap, so it must be up."""
    client, _ = await make_probe(cache_ready=False)

    response = await client.get("/ready")
    payload = await response.json()

    assert response.status == 503
    assert payload["checks"]["cache"] is False


async def test_ready_never_reports_degraded(make_probe):
    """There is no degraded mode any more: readiness is ready or not_ready."""
    client, _ = await make_probe(cache_ready=False)

    response = await client.get("/ready")
    payload = await response.json()

    assert payload["status"] == "not_ready"


async def test_ready_is_503_while_the_bootstrap_is_incomplete(make_probe):
    client, _ = await make_probe(bootstrap_complete=False)

    response = await client.get("/ready")
    payload = await response.json()

    assert response.status == 503
    assert payload["checks"]["bootstrap"] is False


async def test_ready_is_503_when_a_required_extension_failed(make_probe):
    client, _ = await make_probe(startup_failures=["commands.spirit_commands"])

    response = await client.get("/ready")
    payload = await response.json()

    assert response.status == 503
    assert payload["checks"]["extensions"] is False
    assert payload["failed_extensions"] == ["commands.spirit_commands"]


async def test_ready_is_503_during_shutdown(make_probe):
    client, server = await make_probe()
    server.shutting_down = True

    response = await client.get("/ready")

    assert response.status == 503


async def test_ready_does_not_expose_configuration(make_probe):
    client, _ = await make_probe()

    response = await client.get("/ready")
    payload = await response.json()

    assert set(payload) == {"status", "checks"}
    assert set(payload["checks"]) == {"discord", "bootstrap", "database", "cache", "extensions"}
