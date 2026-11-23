"""Spacebar transport adapter tests.

Two discord.py 2.7.1 behaviours break against a real Spacebar instance and are
covered here so a library upgrade cannot silently reintroduce them:

* ``discord.http.json_or_text`` compares ``content-type`` with strict equality,
  while Spacebar answers ``application/json; charset=utf-8``;
* ``contexts``/``integration_types`` are serialized as ``null``, while the
  Spacebar schema requires arrays and answers HTTP 400 (code 50035).

The command tests assert on the payload produced by ``Command.to_dict``, which
is the exact dictionary sent to the API, not on the internal helper alone.
Nothing here contacts a server: the response object and the command tree are
stubs.
"""

import pytest

import discord.http as http_module
from discord import app_commands
from discord.app_commands.installs import AppCommandContext, AppInstallationType

from core.config import Settings
from core.platform import apply_platform_overrides, restore_platform_overrides

REQUIRED_ENV = {
    "SAKURA_BOT_DISCORD_TOKEN": "test-token",
    "SAKURA_BOT_DISCORD_CLIENT_ID": "123456789012345678",
    "SAKURA_BOT_DATABASE_URL": "postgresql+asyncpg://user:password@localhost:5432/sakura_bot",
    "SAKURA_BOT_REDIS_URL": "redis://localhost:6379/0",
    "SAKURA_BOT_OPENAI_API_KEY": "test-openai-key",
}

PLATFORM_ENV = {
    "SAKURA_BOT_PLATFORM": "spacebar",
    "SAKURA_BOT_API_BASE_URL": "http://spacebar-api:3001/api/v9",
    "SAKURA_BOT_GATEWAY_URL": "ws://spacebar-gateway:3001",
}


class StubResponse:
    """Minimal stand-in for ``aiohttp.ClientResponse``."""

    def __init__(self, body: str, content_type: str):
        self._body = body
        self.headers = {"content-type": content_type}

    async def text(self, encoding: str = "utf-8") -> str:
        return self._body


class StubTree:
    """Minimal stand-in for ``app_commands.CommandTree``.

    ``Command.to_dict`` reads only these two attributes, so the payload can be
    built without a client, a token or a network connection.
    """

    allowed_contexts = AppCommandContext()
    allowed_installs = AppInstallationType()


async def _noop(interaction):
    """Callback placeholder: ``to_dict`` never invokes it."""


def command_payload() -> dict:
    """Serialize a real chat-input command exactly as it is sent to the API."""
    command = app_commands.Command(name="sakura-test", description="Test command", callback=_noop)
    return command.to_dict(StubTree())


@pytest.fixture(autouse=True)
def restore_after_test():
    """Always undo the patches, even when a test fails halfway."""
    yield
    restore_platform_overrides()


@pytest.fixture
def spacebar_settings(monkeypatch):
    """Complete synthetic environment selecting the spacebar platform."""
    for name in (
        "DISCORD_TOKEN",
        "DISCORD_CLIENT_ID",
        "DATABASE_URL",
        "REDIS_URL",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in {**REQUIRED_ENV, **PLATFORM_ENV}.items():
        monkeypatch.setenv(name, value)
    return Settings()


async def test_library_rejects_charset_suffix_without_the_adapter():
    """Documents the incompatibility: the stock parser returns raw text."""
    # Explicit precondition: this test must observe the library, not a patch
    # left behind by another test.
    restore_platform_overrides()
    response = StubResponse('{"id": "1"}', "application/json; charset=utf-8")

    assert await http_module.json_or_text(response) == '{"id": "1"}'


async def test_adapter_parses_charset_suffix(spacebar_settings):
    apply_platform_overrides(spacebar_settings)
    response = StubResponse('{"id": "1"}', "application/json; charset=utf-8")

    assert await http_module.json_or_text(response) == {"id": "1"}


async def test_adapter_keeps_bare_json_working(spacebar_settings):
    apply_platform_overrides(spacebar_settings)
    response = StubResponse('{"id": "1"}', "application/json")

    assert await http_module.json_or_text(response) == {"id": "1"}


async def test_adapter_returns_text_for_other_content_types(spacebar_settings):
    apply_platform_overrides(spacebar_settings)
    response = StubResponse("not json", "text/plain")

    assert await http_module.json_or_text(response) == "not json"


def test_command_payload_sends_null_without_the_adapter():
    """Documents the incompatibility at payload level: both keys are ``null``."""
    restore_platform_overrides()
    payload = command_payload()

    assert payload["contexts"] is None
    assert payload["integration_types"] is None


def test_command_payload_sends_arrays_in_spacebar_mode(spacebar_settings):
    """The patch must reach the serialized payload, not only the helper."""
    apply_platform_overrides(spacebar_settings)
    payload = command_payload()

    assert payload["contexts"] == []
    assert payload["integration_types"] == []


def test_restore_brings_back_the_library_payload(spacebar_settings):
    apply_platform_overrides(spacebar_settings)
    assert command_payload()["contexts"] == []

    restore_platform_overrides()

    assert command_payload()["contexts"] is None


def test_contexts_are_sent_as_arrays(spacebar_settings):
    apply_platform_overrides(spacebar_settings)

    assert AppCommandContext()._merge_to_array(None) == []
    assert AppInstallationType()._merge_to_array(None) == []


def test_contexts_keep_explicit_values(spacebar_settings):
    apply_platform_overrides(spacebar_settings)

    assert AppCommandContext(guild=True)._merge_to_array(None) == [AppCommandContext.GUILD]


def test_apply_and_restore_are_idempotent(spacebar_settings):
    apply_platform_overrides(spacebar_settings)
    apply_platform_overrides(spacebar_settings)

    restore_platform_overrides()

    assert AppCommandContext()._merge_to_array(None) is None
    assert AppInstallationType()._merge_to_array(None) is None
