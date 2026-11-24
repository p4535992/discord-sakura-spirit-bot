"""Spacebar transport adapter tests.

Five discord.py 2.7.1 behaviours break against a real Spacebar instance and are
covered here so a library upgrade cannot silently reintroduce them:

* ``discord.http.json_or_text`` compares ``content-type`` with strict equality,
  while Spacebar answers ``application/json; charset=utf-8``;
* ``contexts``/``integration_types`` are serialized as ``null``, while the
  Spacebar schema requires arrays and answers HTTP 400 (code 50035);
* ``Embed.to_dict`` always emits ``flags``, which the Spacebar embed schema
  rejects on the interaction callback (HTTP 400, code 50035), so the command runs
  but the reply never reaches the channel;
* the callback answers ``204 No Content`` while discord.py expects a JSON body,
  so a delivered reply still raises ``TypeError`` afterwards;
* Spacebar rejects the type-5 defer callback (HTTP 400, code 50006) and has no
  followup webhook (HTTP 404, code 10015), so the reply must be the initial
  response.

The command tests assert on the payload produced by ``Command.to_dict``, which
is the exact dictionary sent to the API, not on the internal helper alone.
Nothing here contacts a server: the response object and the command tree are
stubs.
"""

import pytest

import asyncio

import discord
import discord.http as http_module
import discord.interactions as interactions_module
from discord import app_commands
from discord.app_commands.installs import AppCommandContext, AppInstallationType
from discord.enums import InteractionType

from core.config import Settings
from core.platform import apply_platform_overrides, restore_platform_overrides

REQUIRED_ENV = {
    "SAKURA_BOT_DISCORD_TOKEN": "test-token",
    "SAKURA_BOT_DISCORD_CLIENT_ID": "123456789012345678",
    "SAKURA_BOT_DATABASE_URL": "postgresql+asyncpg://user:password@localhost:5432/sakura_bot",
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


def test_embed_payload_keeps_flags_without_the_adapter():
    """Documents the incompatibility: the stock serializer emits ``flags``."""
    restore_platform_overrides()

    assert "flags" in discord.Embed(title="Sakura").to_dict()


def test_embed_payload_drops_flags_in_spacebar_mode(spacebar_settings):
    """The callback schema rejects the extra property, so the reply is dropped."""
    apply_platform_overrides(spacebar_settings)

    payload = discord.Embed(title="Sakura", description="Spirit online").to_dict()

    assert "flags" not in payload
    assert payload["title"] == "Sakura"


def test_restore_brings_back_the_embed_flags(spacebar_settings):
    apply_platform_overrides(spacebar_settings)
    assert "flags" not in discord.Embed(title="Sakura").to_dict()

    restore_platform_overrides()

    assert "flags" in discord.Embed(title="Sakura").to_dict()


class _Parent:
    """Stand-in for the interaction a response belongs to."""

    id = 1234
    type = InteractionType.application_command


class _RecordingResponse:
    def __init__(self):
        self.calls = []

    async def send_message(self, content=None, **kwargs):
        self.calls.append((content, kwargs))
        return "sent"


def _callback_stub():
    """Build a stub bound to the *current* ``_update`` implementation."""
    stub_type = type("CallbackStub", (), {"_parent": _Parent()})
    stub_type._update = interactions_module.InteractionCallbackResponse._update
    return stub_type()


def _response_stub():
    """Build a stub bound to the *current* ``defer`` implementation."""
    stub_type = type("ResponseStub", (), {"_response_type": None, "_parent": _Parent()})
    stub_type.defer = interactions_module.InteractionResponse.defer
    return stub_type()


def _interaction_stub():
    """Build a stub bound to the *current* ``followup`` descriptor."""
    stub_type = type("InteractionStub", (), {})
    stub_type.followup = interactions_module.Interaction.followup

    stub = stub_type()
    stub.response = _RecordingResponse()
    return stub


def test_callback_response_rejects_an_empty_body_without_the_adapter():
    """Documents the incompatibility: the stock parser expects a JSON object."""
    restore_platform_overrides()

    with pytest.raises(TypeError):
        _callback_stub()._update("")


def test_callback_response_tolerates_an_empty_body(spacebar_settings):
    """Spacebar answers 204, so the delivered reply must not raise afterwards."""
    apply_platform_overrides(spacebar_settings)

    stub = _callback_stub()
    stub._update("")

    assert stub.id == 1234
    assert stub.resource is None
    assert stub.message_id is None


def test_defer_is_skipped_for_application_commands(spacebar_settings):
    """The type-5 callback is rejected, so the initial response stays available."""
    apply_platform_overrides(spacebar_settings)

    stub = _response_stub()

    assert asyncio.run(stub.defer()) is None
    assert stub._response_type is None


def test_followup_is_routed_to_the_initial_response(spacebar_settings):
    """Spacebar has no followup webhook, so the reply goes out as the response."""
    apply_platform_overrides(spacebar_settings)

    interaction = _interaction_stub()
    asyncio.run(interaction.followup.send(embed="EMBED", ephemeral=True))

    assert interaction.response.calls == [(None, {"embed": "EMBED", "ephemeral": True})]


def test_restore_brings_back_the_library_interaction_helpers(spacebar_settings):
    apply_platform_overrides(spacebar_settings)
    assert isinstance(interactions_module.Interaction.__dict__["followup"], property)

    restore_platform_overrides()

    assert isinstance(
        interactions_module.Interaction.__dict__["followup"],
        discord.utils.CachedSlotProperty,
    )
