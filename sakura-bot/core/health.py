"""
Minimal HTTP health endpoint used by container orchestration.

``/health`` reports process liveness, ``/ready`` reports whether the bot can
serve traffic (database reachable, required extensions loaded, cache available
when ``SAKURA_BOT_CACHE_REQUIRED`` is true). No configuration value or user data is
exposed.
"""
import logging
from typing import Optional

from aiohttp import web

from core.cache import cache
from core.config import settings
from core.database import db

logger = logging.getLogger(__name__)


class HealthServer:
    """Small aiohttp server exposing liveness and readiness probes."""

    def __init__(self):
        self._runner: Optional[web.AppRunner] = None
        self.startup_failures: list[str] = []

    async def start(self):
        """Start the server when enabled by configuration."""
        if not settings.health_server_enabled:
            logger.info("Health endpoint disabled by configuration")
            return

        app = web.Application()
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/ready", self._handle_ready)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, settings.health_host, settings.health_port)
        await site.start()
        logger.info(
            "Health endpoint listening on %s:%s",
            settings.health_host,
            settings.health_port,
        )

    async def stop(self):
        """Stop the server and release the listening socket."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            logger.info("Health endpoint stopped")

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def _handle_ready(self, request: web.Request) -> web.Response:
        database_ready = await db.ping()
        cache_ready = cache.redis is not None
        extensions_ready = not self.startup_failures
        ready = database_ready and extensions_ready and (
            cache_ready or not settings.cache_required
        )

        payload = {
            "status": "ready" if ready else "not_ready",
            "checks": {
                "database": database_ready,
                "cache": cache_ready,
                "extensions": extensions_ready,
            },
        }
        if self.startup_failures:
            payload["failed_extensions"] = list(self.startup_failures)

        return web.json_response(payload, status=200 if ready else 503)


health_server = HealthServer()
