"""Minimal discord.py 2.7.1 spike against a local Spacebar instance.

This is the FASE 0 proof of concept for docs/SPACEBAR_COMPATIBILITY.md. It is
not part of the pytest suite: it needs a running Spacebar stack.

What it proves, in order:
  1. the REST base can be redirected to Spacebar (``discord.http.Route.BASE``);
  2. the Gateway can be redirected (``DiscordWebSocket.DEFAULT_GATEWAY``);
  3. Identify/READY completes and the bot sees its guild;
  4. a message can be sent through the API;
  5. an application command can be registered and fetched back.

What it does NOT prove: interaction dispatch (needs a real client clicking the
command), ephemeral responses, embeds rendering, reactions and voice events.

Run from the repository root, with the beta stack up:

    .\\.venv\\Scripts\\python.exe spacebar-beta\\spike\\discord_py_spike.py
"""

import asyncio
import os
import pathlib
import sys
import traceback

import discord
import yarl
from discord.ext import commands
from discord.gateway import DiscordWebSocket
from discord.http import Route

ENV_FILE = pathlib.Path(__file__).resolve().parents[2] / ".env.spacebar"

API_BASE = os.environ.get("SPACEBAR_API_BASE_URL", "http://127.0.0.1:3002/api/v9")
GATEWAY_URL = os.environ.get("SPACEBAR_GATEWAY_URL", "ws://127.0.0.1:3001/")

STEPS: list[tuple[str, str]] = []


def record(step: str, result: str) -> None:
    """Collect one PASS/FAIL line for the final summary."""
    STEPS.append((step, result))
    print(f"[{result}] {step}", flush=True)


def read_token() -> str:
    """Read the Spacebar bot token from the gitignored local env file."""
    if not ENV_FILE.is_file():
        raise SystemExit(f"missing {ENV_FILE.name}: create it from .env.spacebar.example")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("SPACEBAR_BOT_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("SPACEBAR_BOT_TOKEN is not set in .env.spacebar")


def patch_json_parsing() -> None:
    """Accept ``application/json; charset=utf-8`` as JSON.

    discord.py 2.7.1 compares the header with strict equality
    (``discord/http.py``, ``json_or_text``), so Spacebar's charset-suffixed
    header makes every response come back as a raw string instead of a dict.
    Discord.com sends the bare ``application/json``, which is why the bug never
    shows up against the real service.
    """
    import discord.http as http_module
    import discord.utils as utils_module

    async def json_or_text(response):
        text = await response.text(encoding="utf-8")
        content_type = response.headers.get("content-type", "")
        if content_type.split(";")[0].strip().lower() == "application/json":
            return utils_module._from_json(text)
        return text

    http_module.json_or_text = json_or_text


def patch_app_command_payload() -> None:
    """Send empty arrays instead of ``null`` for ``contexts``/``integration_types``.

    discord.py 2.7.1 always includes both keys in the command payload and sets
    them to ``null`` when the command does not restrict them. Spacebar's schema
    requires arrays and answers HTTP 400 (code 50035, "must be array").
    """
    from discord.app_commands.installs import AppCommandContext, AppInstallationType

    for cls in (AppCommandContext, AppInstallationType):
        original = cls._merge_to_array

        def patched(self, other, _original=original):
            return _original(self, other) or []

        cls._merge_to_array = patched


def patch_transport() -> None:
    """Point discord.py at the local Spacebar instance.

    ``Route.BASE`` is read when a Route is built, so patching the class
    attribute after import is enough. ``Client.connect`` never passes a gateway
    to ``DiscordWebSocket.from_client``, so the class default is the only hook.
    """
    Route.BASE = API_BASE
    DiscordWebSocket.DEFAULT_GATEWAY = yarl.URL(GATEWAY_URL)
    patch_json_parsing()
    patch_app_command_payload()


async def main() -> int:
    """Run the spike and return a process exit code."""
    token = read_token()
    patch_transport()
    record("REST base redirected", f"PASS ({Route.BASE})")
    record("Gateway redirected", f"PASS ({DiscordWebSocket.DEFAULT_GATEWAY})")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.presences = True
    intents.voice_states = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.tree.command(name="sakura-spike", description="Spacebar transport spike")
    async def sakura_spike(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("spike ok", ephemeral=True)

    async def on_ready() -> None:
        record("READY received", f"PASS (user={bot.user} id={bot.user.id})")
        guilds = list(bot.guilds)
        record(
            "Guild visible to the bot",
            f"PASS ({len(guilds)} guild(s): {[g.name for g in guilds]})"
            if guilds
            else "FAIL (no guild: autoJoin did not add the bot)",
        )

        if guilds:
            guild = guilds[0]
            record(
                "Channels visible",
                f"PASS ({len(guild.text_channels)} text, {len(guild.voice_channels)} voice)",
            )
            channel = guild.text_channels[0] if guild.text_channels else None
            if channel is None:
                record("Send message", "FAIL (no text channel)")
            else:
                try:
                    message = await asyncio.wait_for(
                        channel.send("Sakura spike: transport online 🌸"), timeout=20
                    )
                    record("Send message", f"PASS (id={message.id} in #{channel.name})")
                except Exception as exc:  # noqa: BLE001 - reported, not raised
                    record("Send message", f"FAIL ({type(exc).__name__}: {exc})")

        try:
            synced = await asyncio.wait_for(bot.tree.sync(), timeout=30)
            record("Slash command sync", f"PASS ({len(synced)} command(s) synced)")
        except Exception as exc:  # noqa: BLE001
            record("Slash command sync", f"FAIL ({type(exc).__name__}: {exc})")

        try:
            fetched = await asyncio.wait_for(bot.tree.fetch_commands(), timeout=30)
            names = sorted(c.name for c in fetched)
            record("Slash command fetch", f"PASS ({names})")
        except Exception as exc:  # noqa: BLE001
            record("Slash command fetch", f"FAIL ({type(exc).__name__}: {exc})")

        await bot.close()

    bot.event(on_ready)

    try:
        await asyncio.wait_for(bot.start(token), timeout=90)
    except asyncio.TimeoutError:
        record("Gateway session", "FAIL (timeout after 90s)")
    except Exception as exc:  # noqa: BLE001
        record("Gateway session", f"FAIL ({type(exc).__name__}: {exc})")
        traceback.print_exc()
    finally:
        if not bot.is_closed():
            await bot.close()

    print("\n=== SPIKE SUMMARY ===", flush=True)
    for step, result in STEPS:
        print(f"{result:<8} {step}", flush=True)
    failed = [s for s, r in STEPS if r.startswith("FAIL")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
