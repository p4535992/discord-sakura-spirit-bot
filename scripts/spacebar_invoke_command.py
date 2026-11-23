"""Invoke a Sakura slash command on the local Spacebar beta stack.

A Discord client triggers a slash command by posting to ``/interactions``; this
script sends the same request, so a command can be exercised without the web
client. It then reads the channel to show the public reply. An ephemeral reply
never reaches the channel history, so for those the evidence is "no new message
and no exception in the bot log".

Usage (from the repository root, with the stack running):

    .\\.venv\\Scripts\\python.exe scripts\\spacebar_invoke_command.py sakura-help --new-user
    .\\.venv\\Scripts\\python.exe scripts\\spacebar_invoke_command.py sakura-spirit-interact ^
        --new-user --option "message=Ciao spirito"

The bot token and the application id are read from ``.env.spacebar``; neither is
printed. Exit code 1 means the interaction was not accepted.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import string
import sys
import time
import urllib.error
import urllib.request

DEFAULT_API = "http://127.0.0.1:3002/api/v9"
ENV_FILE = ".env.spacebar"
ROOT = pathlib.Path(__file__).resolve().parent.parent

# Embeds carry emoji: a cp1252 console would fail while printing them.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_env(name: str) -> str:
    """Return ``name`` from the local env file without exporting anything."""
    for line in (ROOT / ENV_FILE).read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"{name} is missing from {ENV_FILE}")


def call(method, path, token=None, body=None, api=DEFAULT_API):
    """Perform one REST call and return ``(status, parsed_body)``."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(api + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", token)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:300]


def register_user(api):
    """Create a throwaway local account and return its token."""
    suffix = "".join(random.choices(string.digits, k=6))
    status, payload = call(
        "POST",
        "/auth/register",
        body={
            "username": f"sakurainvoke{suffix}",
            "password": "SakuraInvoke11",
            "date_of_birth": "2000-01-01",
            "consent": True,
        },
        api=api,
    )
    if status != 200 or not isinstance(payload, dict) or "token" not in payload:
        raise SystemExit(f"registration failed: HTTP {status} {payload}")
    return payload["token"]


def parse_options(pairs):
    """Turn ``name=value`` arguments into chat-input options."""
    options = []
    for pair in pairs:
        name, _, value = pair.partition("=")
        if not name or not value:
            raise SystemExit(f"--option expects name=value, got '{pair}'")
        options.append({"name": name, "type": 3, "value": value})
    return options


def main(argv=None):
    parser = argparse.ArgumentParser(description="Invoke a slash command on Spacebar")
    parser.add_argument("command", help="slash command name, e.g. sakura-help")
    parser.add_argument("--option", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--new-user", action="store_true", help="register a throwaway user")
    parser.add_argument("--api", default=DEFAULT_API, help=f"REST base (default {DEFAULT_API})")
    parser.add_argument(
        "--wait", type=float, default=6.0, help="seconds before reading the channel"
    )
    args = parser.parse_args(argv)

    bot_token = "Bot " + read_env("SPACEBAR_BOT_TOKEN")
    app_id = read_env("SPACEBAR_BOT_CLIENT_ID")

    status, commands = call("GET", f"/applications/{app_id}/commands", bot_token, api=args.api)
    if status != 200 or not isinstance(commands, list):
        raise SystemExit(f"cannot list commands: HTTP {status} {commands}")
    command = next((item for item in commands if item["name"] == args.command), None)
    if command is None:
        raise SystemExit(f"'{args.command}' is not registered on this instance")

    status, guilds = call("GET", "/users/@me/guilds", bot_token, api=args.api)
    if not guilds:
        raise SystemExit("the bot is not in any guild")
    guild_id = guilds[0]["id"]
    status, channels = call("GET", f"/guilds/{guild_id}/channels", bot_token, api=args.api)
    channel = next((item for item in channels if item["type"] == 0), None)
    if channel is None:
        raise SystemExit(f"guild {guild_id} has no text channel")

    if not args.new_user:
        raise SystemExit("--new-user is required: a bot account cannot invoke a command")
    user_token = register_user(args.api)

    status, before = call(
        "GET", f"/channels/{channel['id']}/messages?limit=20", bot_token, api=args.api
    )
    seen = {message["id"] for message in before or []}

    interaction = {
        "type": 2,
        "application_id": app_id,
        "guild_id": guild_id,
        "channel_id": channel["id"],
        "session_id": "".join(random.choices(string.hexdigits.lower(), k=32)),
        "data": {
            "id": command["id"],
            "name": command["name"],
            "type": 1,
            "options": parse_options(args.option),
            "version": command.get("version", "1"),
        },
    }
    status, payload = call("POST", "/interactions", user_token, interaction, api=args.api)
    print(f"{args.command}: POST /interactions -> HTTP {status} {payload or ''}".rstrip())
    if status not in (200, 204):
        return 1

    time.sleep(args.wait)
    status, after = call(
        "GET", f"/channels/{channel['id']}/messages?limit=20", bot_token, api=args.api
    )
    new_messages = [message for message in after or [] if message["id"] not in seen]
    print(f"new messages in #{channel.get('name')}: {len(new_messages)}")
    for message in new_messages:
        author = message.get("author", {})
        embeds = message.get("embeds") or []
        titles = [embed.get("title") for embed in embeds]
        content = (message.get("content") or "").replace("\n", " ")[:160]
        print(f"  from={author.get('username')} bot={author.get('bot')} embeds={len(embeds)}")
        print(f"  titles={titles}")
        print(f"  content={content!r}")
    if not new_messages:
        print("  (no channel message: ephemeral reply, or silent failure in the bot log)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
