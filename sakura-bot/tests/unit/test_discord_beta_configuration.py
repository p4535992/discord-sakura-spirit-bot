"""Discord beta stack and configuration tests.

The beta must stay isolated from production and must never publish slash
commands globally. Nothing here contacts Discord: the compose file is inspected
as text (PyYAML is not a project dependency), the settings are built with
``_env_file=None`` so a developer ``.env`` cannot influence them, and the
command tree is replaced by a recorder.
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import core.ai_provider as ai_provider
from core.ai_provider import (
    AIProviderConfigurationError,
    SPIRIT_PERSONALITY_KIND,
    SPIRIT_RESPONSE_KIND,
    STUB_ANSWERS,
    USER_EMOTION_KIND,
    validate_ai_provider,
)
from core.bot import SakuraSpiritBot, resolve_command_sync_guild
from core.config import Settings, is_discord_beta, settings
from systems.spirits.spirit_ai import SpiritAI

# The Docker test runner mounts only the repository files asserted below, so the
# clone root is passed explicitly there; on the host it is derived from this file.
REPOSITORY_ROOT = Path(
    os.environ.get("SAKURA_REPOSITORY_ROOT") or Path(__file__).resolve().parents[3]
)
BETA_COMPOSE = REPOSITORY_ROOT / "docker-compose.discord-beta.yml"
BETA_ENV_TEMPLATE = REPOSITORY_ROOT / ".env.discord-beta.example"
GITIGNORE = REPOSITORY_ROOT / ".gitignore"

TEST_GUILD_ID = 123456789012345678


def _services() -> dict[str, str]:
    """Split the beta compose file into ``{service: block}`` without a YAML parser."""
    blocks: dict[str, list[str]] = {}
    current: list[str] | None = None
    in_services = False
    for line in BETA_COMPOSE.read_text(encoding="utf-8").splitlines():
        if line == "services:":
            in_services = True
            continue
        if line and not line.startswith(" "):
            in_services = False
            current = None
            continue
        if not in_services:
            continue
        if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            current = blocks.setdefault(line.strip().rstrip(":"), [])
            continue
        if current is not None:
            current.append(line)
    return {name: "\n".join(lines) for name, lines in blocks.items()}


# --- Compose isolation -------------------------------------------------------


def test_beta_compose_uses_its_own_project_name():
    text = BETA_COMPOSE.read_text(encoding="utf-8")

    assert "name: sakura-spirit-bot-discord-beta" in text


def test_beta_compose_declares_the_three_beta_services():
    assert set(_services()) == {"beta-postgres", "beta-redis", "beta-bot"}


def test_beta_compose_avoids_container_names_and_published_ports():
    text = BETA_COMPOSE.read_text(encoding="utf-8")

    assert "container_name:" not in text
    assert "\n    ports:" not in text


def test_beta_compose_shares_no_production_resource():
    text = BETA_COMPOSE.read_text(encoding="utf-8")

    for production_resource in (
        "sakura-postgres-data",
        "sakura-bot-logs",
        "sakura-proxy",
        "sakura-platform",
    ):
        assert production_resource not in text


def test_only_the_bot_joins_the_egress_network():
    services = _services()

    assert "- beta-private" in services["beta-bot"]
    assert "- beta-egress" in services["beta-bot"]
    for name in ("beta-postgres", "beta-redis"):
        assert "- beta-private" in services[name]
        assert "beta-egress" not in services[name]


def test_private_network_is_internal():
    text = BETA_COMPOSE.read_text(encoding="utf-8")

    assert "beta-private:\n    internal: true" in text


# --- Environment template and ignore rules -----------------------------------


def test_beta_env_template_keeps_placeholders_for_the_secrets():
    text = BETA_ENV_TEMPLATE.read_text(encoding="utf-8")

    for name in (
        "SAKURA_BETA_DISCORD_TOKEN",
        "SAKURA_BETA_DISCORD_CLIENT_ID",
        "SAKURA_BETA_TEST_GUILD_ID",
    ):
        assert f"{name}=INSERISCI" in text
    assert "SAKURA_BETA_AI_PROVIDER=stub" in text


def test_beta_env_file_is_ignored_by_git():
    ignored = {line.strip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()}

    assert "/.env.discord-beta" in ignored
    assert "/.env.discord-beta.*.local" in ignored


# --- Settings ----------------------------------------------------------------


def test_test_guild_id_is_parsed_as_an_integer(monkeypatch):
    monkeypatch.setenv("SAKURA_BOT_TEST_GUILD_ID", str(TEST_GUILD_ID))

    assert Settings(_env_file=None).test_guild_id == TEST_GUILD_ID


def test_test_guild_id_is_optional(monkeypatch):
    monkeypatch.delenv("SAKURA_BOT_TEST_GUILD_ID", raising=False)

    assert Settings(_env_file=None).test_guild_id is None


def test_ai_provider_defaults_to_openai(monkeypatch):
    monkeypatch.delenv("SAKURA_BOT_AI_PROVIDER", raising=False)

    assert Settings(_env_file=None).ai_provider == "openai"


def test_ai_provider_is_normalized(monkeypatch):
    monkeypatch.setenv("SAKURA_BOT_AI_PROVIDER", "  Stub ")

    assert Settings(_env_file=None).ai_provider == "stub"


def test_stub_provider_does_not_require_an_openai_key(monkeypatch):
    monkeypatch.setenv("SAKURA_BOT_AI_PROVIDER", "stub")
    monkeypatch.delenv("SAKURA_BOT_OPENAI_API_KEY", raising=False)

    assert Settings(_env_file=None).openai_api_key is None


def test_openai_provider_still_requires_its_key(monkeypatch):
    monkeypatch.delenv("SAKURA_BOT_AI_PROVIDER", raising=False)
    monkeypatch.delenv("SAKURA_BOT_OPENAI_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="SAKURA_BOT_OPENAI_API_KEY"):
        Settings(_env_file=None)


def test_template_placeholders_are_rejected(monkeypatch):
    monkeypatch.setenv("SAKURA_BOT_DISCORD_TOKEN", "INSERISCI_TOKEN_DEL_BOT_BETA")

    with pytest.raises(ValidationError, match="template placeholders"):
        Settings(_env_file=None)


def test_placeholder_guild_id_is_rejected(monkeypatch):
    monkeypatch.setenv("SAKURA_BOT_TEST_GUILD_ID", "INSERISCI_GUILD_ID_DEL_SERVER_BETA")

    with pytest.raises(ValidationError, match="SAKURA_BOT_TEST_GUILD_ID"):
        Settings(_env_file=None)


def test_discord_beta_environment_is_recognized(monkeypatch):
    monkeypatch.setattr(settings, "environment", "  Discord-Beta ")
    assert is_discord_beta() is True

    monkeypatch.setattr(settings, "environment", "production")
    assert is_discord_beta() is False


def test_unknown_ai_provider_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "claude")

    with pytest.raises(AIProviderConfigurationError, match="AI_PROVIDER must be one of"):
        validate_ai_provider(settings)


@pytest.mark.parametrize("provider", ["openai", "stub"])
def test_supported_ai_providers_are_accepted(monkeypatch, provider):
    monkeypatch.setattr(settings, "ai_provider", provider)

    validate_ai_provider(settings)


# --- Slash command sync scope ------------------------------------------------


class _TreeRecorder:
    """Records the sync target instead of uploading anything to Discord."""

    def __init__(self) -> None:
        self.copied_to: list[int] = []
        self.synced_with: list[int | None] = []

    def copy_global_to(self, *, guild) -> None:
        self.copied_to.append(guild.id)

    async def sync(self, *, guild=None) -> list:
        self.synced_with.append(None if guild is None else guild.id)
        return []


@pytest.fixture
async def bot_with_recorder(monkeypatch):
    """Bot whose command tree only records calls: nothing is uploaded.

    ``Bot.tree`` is a read-only property, so the two methods are replaced on the
    real tree instance instead of swapping the tree itself.
    """
    bot = SakuraSpiritBot()
    recorder = _TreeRecorder()
    monkeypatch.setattr(bot.tree, "sync", recorder.sync)
    monkeypatch.setattr(bot.tree, "copy_global_to", recorder.copy_global_to)
    try:
        yield bot, recorder
    finally:
        await bot.close()


async def test_beta_syncs_only_the_test_guild(monkeypatch, bot_with_recorder):
    bot, tree = bot_with_recorder
    monkeypatch.setattr(settings, "environment", "discord-beta")
    monkeypatch.setattr(settings, "test_guild_id", TEST_GUILD_ID)

    guild = resolve_command_sync_guild()
    await bot._sync_application_commands(guild)

    assert guild.id == TEST_GUILD_ID
    assert tree.copied_to == [TEST_GUILD_ID]
    assert tree.synced_with == [TEST_GUILD_ID]


async def test_production_keeps_the_global_sync(monkeypatch, bot_with_recorder):
    bot, tree = bot_with_recorder
    monkeypatch.setattr(settings, "environment", "production")
    # A leftover beta variable must not narrow the production scope.
    monkeypatch.setattr(settings, "test_guild_id", TEST_GUILD_ID)

    guild = resolve_command_sync_guild()
    await bot._sync_application_commands(guild)

    assert guild is None
    assert tree.copied_to == []
    assert tree.synced_with == [None]


async def test_beta_without_guild_id_fails_closed(monkeypatch, bot_with_recorder):
    _, tree = bot_with_recorder
    monkeypatch.setattr(settings, "environment", "discord-beta")
    monkeypatch.setattr(settings, "test_guild_id", None)

    with pytest.raises(RuntimeError, match="SAKURA_BOT_TEST_GUILD_ID is required"):
        resolve_command_sync_guild()

    assert tree.synced_with == []


# --- AI provider -------------------------------------------------------------


async def test_stub_provider_answers_without_creating_a_client(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "stub")
    monkeypatch.setattr(ai_provider, "_client", None)

    def _forbidden_client(*args, **kwargs):
        raise AssertionError("the stub provider must not create an OpenAI client")

    monkeypatch.setattr(ai_provider, "AsyncOpenAI", _forbidden_client)

    reply = await SpiritAI.generate_spirit_response(
        spirit_name="Hanami",
        personality="mysterious",
        faction="Moonborn",
        mood="Peaceful",
        user_message="hello",
    )

    assert reply == STUB_ANSWERS[SPIRIT_RESPONSE_KIND]
    assert ai_provider._client is None


async def test_stub_personality_and_emotion_are_deterministic(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "stub")

    personality = await SpiritAI.generate_spirit_personality("rare", "Moonborn", "water")
    emotion = await SpiritAI.analyze_user_emotion(["I feel great today"])

    assert personality == json.loads(STUB_ANSWERS[SPIRIT_PERSONALITY_KIND])
    assert emotion == json.loads(STUB_ANSWERS[USER_EMOTION_KIND])


async def test_stub_rejects_an_unknown_request_kind(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "stub")

    with pytest.raises(ValueError, match="No stub answer is defined"):
        await ai_provider.complete(kind="unknown", messages=[], max_tokens=1, temperature=0.0)


async def test_openai_provider_still_uses_the_configured_model(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-openai-key")
    monkeypatch.setattr(settings, "openai_base_url", None)
    monkeypatch.setattr(ai_provider, "_client", None)

    requests: list[dict] = []

    class _Completions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            message = SimpleNamespace(content="  from the fake client  ")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    created: list = []

    class _Client:
        def __init__(self, **options):
            self.options = options
            self.chat = SimpleNamespace(completions=_Completions())

    def _factory(**options):
        client = _Client(**options)
        created.append(client)
        return client

    monkeypatch.setattr(ai_provider, "AsyncOpenAI", _factory)

    reply = await SpiritAI.generate_spirit_response(
        spirit_name="Hanami",
        personality="mysterious",
        faction="Moonborn",
        mood="Peaceful",
        user_message="hello",
    )

    assert reply == "from the fake client"
    assert created[0].options["api_key"] == "test-openai-key"
    assert requests[0]["model"] == settings.openai_model
