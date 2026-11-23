"""Platform selection and transport overrides.

Production keeps the discord.py defaults: with ``SAKURA_BOT_PLATFORM=discord``
nothing is patched and the bootstrap is the same as before. The ``spacebar``
mode exists for the local beta stack in ``docker-compose.spacebar.yml`` and
requires explicit endpoints, so a misconfiguration fails at startup instead of
silently reaching discord.com.

Spacebar is Discord-compatible only up to a point. Three gaps are worked around
here, each one reproduced against a running instance (see
``docs/SPACEBAR_COMPATIBILITY.md``):

* ``Route.BASE`` is a class attribute hardcoded to ``https://discord.com/api/v10``;
* ``Client.connect`` never passes a gateway to ``DiscordWebSocket.from_client``,
  so ``DEFAULT_GATEWAY`` is the only hook;
* Spacebar answers ``application/json; charset=utf-8`` and requires arrays for
  ``contexts``/``integration_types``, while discord.py 2.7.1 compares the header
  with strict equality and sends ``null``.

Every patch is applied only in ``spacebar`` mode and can be reverted with
:func:`restore_platform_overrides`, which the tests use to stay order
independent.
"""

import logging
from typing import Any, Optional
from urllib.parse import urlparse

import yarl
from discord.app_commands.installs import AppCommandContext, AppInstallationType
from discord.asset import Asset
from discord.gateway import DiscordWebSocket
from discord.http import Route

from core.config import Settings

logger = logging.getLogger(__name__)

DISCORD_PLATFORM = "discord"
SPACEBAR_PLATFORM = "spacebar"
SUPPORTED_PLATFORMS = (DISCORD_PLATFORM, SPACEBAR_PLATFORM)

# Hosts that a beta instance must never point at: reaching them means the
# configuration is wrong and the run would leave the local network.
FORBIDDEN_HOST_SUFFIXES = (
    "discord.com",
    "discordapp.com",
    "discordapp.net",
    "discord.gg",
    "openai.com",
)

# Filled by the first apply and consumed by restore, so a second apply does not
# wrap an already patched callable.
_ORIGINALS: dict[str, Any] = {}


class PlatformConfigurationError(RuntimeError):
    """Raised when the selected platform cannot be configured safely."""


def _host_of(url: str) -> str:
    """Return the lowercased host of ``url`` without the port."""
    parsed = urlparse(url)
    return (parsed.hostname or "").lower()


def _is_forbidden_host(host: str) -> bool:
    """True when ``host`` belongs to a public service the beta must not reach."""
    return any(host == suffix or host.endswith("." + suffix) for suffix in FORBIDDEN_HOST_SUFFIXES)


def _require_url(value: Optional[str], setting: str, schemes: tuple[str, ...]) -> str:
    """Validate one endpoint override and return it without trailing slashes."""
    if not value or not value.strip():
        raise PlatformConfigurationError(
            f"SAKURA_BOT_{setting} is required when SAKURA_BOT_PLATFORM=spacebar"
        )

    cleaned = value.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in schemes:
        raise PlatformConfigurationError(
            f"SAKURA_BOT_{setting} must use one of {', '.join(schemes)}, got scheme '{parsed.scheme}'"
        )
    if not parsed.hostname:
        raise PlatformConfigurationError(f"SAKURA_BOT_{setting} has no host: '{cleaned}'")
    if _is_forbidden_host(parsed.hostname.lower()):
        raise PlatformConfigurationError(
            f"SAKURA_BOT_{setting} points at a public service host ('{parsed.hostname}'); "
            "the spacebar platform must stay local"
        )
    return cleaned


def validate_platform_settings(settings: Settings) -> None:
    """Reject an unusable platform configuration before anything is patched."""
    platform = (settings.platform or "").strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise PlatformConfigurationError(
            f"SAKURA_BOT_PLATFORM must be one of {', '.join(SUPPORTED_PLATFORMS)}, got '{settings.platform}'"
        )
    if platform == DISCORD_PLATFORM:
        return

    _require_url(settings.api_base_url, "API_BASE_URL", ("http", "https"))
    _require_url(settings.gateway_url, "GATEWAY_URL", ("ws", "wss"))
    if settings.asset_base_url:
        _require_url(settings.asset_base_url, "ASSET_BASE_URL", ("http", "https"))


def _patch_json_parsing() -> None:
    """Accept ``application/json; charset=utf-8`` as JSON.

    ``discord.http.json_or_text`` compares the header with strict equality, so
    Spacebar's charset suffix makes every response a raw string and the client
    fails while parsing the bot user.
    """
    import discord.http as http_module
    import discord.utils as utils_module

    if "json_or_text" in _ORIGINALS:
        return

    async def json_or_text(response):
        text = await response.text(encoding="utf-8")
        content_type = response.headers.get("content-type", "")
        if content_type.split(";")[0].strip().lower() == "application/json":
            return utils_module._from_json(text)
        return text

    _ORIGINALS["json_or_text"] = (http_module, "json_or_text", http_module.json_or_text)
    http_module.json_or_text = json_or_text


def _patch_app_command_payload() -> None:
    """Send empty arrays instead of ``null`` for ``contexts``/``integration_types``.

    discord.py 2.7.1 always includes both keys and leaves them ``null`` when the
    command does not restrict them; Spacebar's schema requires arrays and
    answers HTTP 400 (code 50035, "must be array").
    """
    for cls in (AppCommandContext, AppInstallationType):
        key = f"_merge_to_array:{cls.__name__}"
        if key in _ORIGINALS:
            continue

        original = cls._merge_to_array

        def patched(self, other, _original=original):
            return _original(self, other) or []

        _ORIGINALS[key] = (cls, "_merge_to_array", original)
        cls._merge_to_array = patched


def apply_platform_overrides(settings: Settings) -> None:
    """Validate the platform configuration and patch the transport if needed."""
    validate_platform_settings(settings)
    platform = (settings.platform or "").strip().lower()

    if platform == DISCORD_PLATFORM:
        logger.debug("Platform 'discord': library defaults kept, nothing patched")
        return

    api_base = _require_url(settings.api_base_url, "API_BASE_URL", ("http", "https"))
    gateway_url = _require_url(settings.gateway_url, "GATEWAY_URL", ("ws", "wss"))

    _ORIGINALS.setdefault("Route.BASE", (Route, "BASE", Route.BASE))
    Route.BASE = api_base

    _ORIGINALS.setdefault(
        "DiscordWebSocket.DEFAULT_GATEWAY",
        (DiscordWebSocket, "DEFAULT_GATEWAY", DiscordWebSocket.DEFAULT_GATEWAY),
    )
    DiscordWebSocket.DEFAULT_GATEWAY = yarl.URL(gateway_url + "/")

    if settings.asset_base_url:
        asset_base = _require_url(settings.asset_base_url, "ASSET_BASE_URL", ("http", "https"))
        _ORIGINALS.setdefault("Asset.BASE", (Asset, "BASE", Asset.BASE))
        Asset.BASE = asset_base

    _patch_json_parsing()
    _patch_app_command_payload()

    logger.info(
        "Spacebar transport active: REST %s, gateway %s, assets %s",
        Route.BASE,
        DiscordWebSocket.DEFAULT_GATEWAY,
        Asset.BASE,
    )


def restore_platform_overrides() -> None:
    """Undo every patch applied by :func:`apply_platform_overrides`."""
    for key, (owner, attribute, original) in list(_ORIGINALS.items()):
        setattr(owner, attribute, original)
        del _ORIGINALS[key]
    logger.debug("Platform overrides restored")
