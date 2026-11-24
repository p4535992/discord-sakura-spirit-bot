"""
HTTP probes used by container orchestration.

``/health`` reports process liveness, ``/ready`` reports whether the bot can
serve traffic: the Discord gateway must be connected, the bootstrap must be
complete, the database must answer a trivial query, the in-process cache must be
initialised and every required extension must be loaded. No configuration value,
credential or user data is exposed.

``checks.cache`` describes the local TTL cache of ``core/cache.py``, not a remote
service. It is kept in the payload for the clients that already read it, but it
never replaces ``checks.database``: only the database query proves that the
persistent state (users, servers, LFG sessions, cooldowns) is reachable.
"""

import logging
from typing import Any, Optional

from aiohttp import web

from core.cache import cache
from core.config import settings
from core.database import db

logger = logging.getLogger(__name__)

READY_STATUS = "ready"
NOT_READY_STATUS = "not_ready"


class HealthServer:
    """Small aiohttp server exposing liveness and readiness probes."""

    def __init__(self):
        self._runner: Optional[web.AppRunner] = None
        self.startup_failures: list[str] = []
        # Readiness stays false until setup_hook has loaded every required
        # extension: an empty ``startup_failures`` alone does not prove that the
        # bootstrap already finished.
        self.bootstrap_complete = False
        self.shutting_down = False
        self._bot: Optional[Any] = None

    def attach(self, bot: Any) -> None:
        """Bind the Discord client; typed as ``Any`` to avoid an import cycle."""
        self._bot = bot

    def create_app(self) -> web.Application:
        """Build the aiohttp application; tests use it without a real socket."""
        app = web.Application()
        app.router.add_get("/health", self.handle_health)
        app.router.add_get("/ready", self.handle_ready)
        return app

    async def start(self):
        """Start the server when enabled by configuration."""
        if not settings.health_server_enabled:
            logger.info("Health endpoint disabled by configuration")
            return

        self._runner = web.AppRunner(self.create_app(), access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, settings.health_host, settings.health_port)
        await site.start()
        logger.info(
            "Health endpoint listening on %s:%s",
            settings.health_host,
            settings.health_port,
        )

    async def stop(self):
        """Stop the server and fail readiness before the clients are closed."""
        self.shutting_down = True
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            logger.info("Health endpoint stopped")

    async def handle_health(self, request: web.Request) -> web.Response:
        """Liveness only: the process answers, whatever the gateway state is."""
        return web.json_response({"status": "ok"})

    async def handle_ready(self, request: web.Request) -> web.Response:
        """Readiness: HTTP 200 only when the bot can actually serve traffic."""
        payload = await self.collect_readiness()
        status = 200 if payload["status"] == READY_STATUS else 503
        return web.json_response(payload, status=status)

    async def collect_readiness(self) -> dict[str, Any]:
        """Return the readiness payload; both probes are time bounded."""
        discord_ready = self._bot is not None and self._bot.is_ready()
        database_ready = await db.ping()
        cache_ready = await cache.ping()
        extensions_ready = not self.startup_failures

        ready = (
            discord_ready
            and database_ready
            and extensions_ready
            and cache_ready
            and self.bootstrap_complete
            and not self.shutting_down
        )
        status = READY_STATUS if ready else NOT_READY_STATUS

        payload: dict[str, Any] = {
            "status": status,
            "checks": {
                "discord": discord_ready,
                "bootstrap": self.bootstrap_complete,
                "database": database_ready,
                "cache": cache_ready,
                "extensions": extensions_ready,
            },
        }
        if self.startup_failures:
            payload["failed_extensions"] = list(self.startup_failures)
        return payload


health_server = HealthServer()
