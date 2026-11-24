# Discord Beta — Windows operator guide

> English is the primary version. Italian translation:
> [DISCORD_BETA_GUIDE_WINDOWS_it.md](DISCORD_BETA_GUIDE_WINDOWS_it.md).

Isolated stack that runs the **real bot code** against **real Discord**, using a
**separate Discord application** and a **private test guild**. It verifies the
slash commands in the Discord client without touching the tokens, guilds, data
or volumes of production.

## Test levels: from no Discord to production

The repository covers the first two levels, and each one answers a different
question.

| Level | Environment | What it proves | Where |
|---|---|---|---|
| 0 | No server | Logic and regressions: settings, sync scope, AI provider, file isolation | `python -m pytest` inside `sakura-bot` |
| 1 | **Self-hosted Spacebar** | Transport: REST, Gateway, registration and **real dispatch** of slash commands, with a mock AI | `docs/SPACEBAR_BETA.md` |
| 2 | **Real Discord, private guild** | Real Discord behaviour: permissions, privileged intents, embed rendering, rate limits | this guide |
| 3 | Production | Real data and load | out of scope |

Level 1 is the "Discord environment" without Discord: a self-hosted compatible
server, no Discord account, no real token, no call to `discord.com` or OpenAI.
Level 1 does **not** replace level 2: Spacebar does not reproduce Discord
permissions, the exact embed rendering, rate limits or the real Gateway. Rule of
thumb: if the question is "does the command work", start at level 1; if the
question is "does it look and behave correctly on Discord", use level 2.

## What it does and what it does not do

| Does | Does not |
|---|---|
| Starts the bot with `SAKURA_BOT_ENVIRONMENT=discord-beta` on the **same code** as production | Does not start, stop or reconfigure the production stack |
| Uses a separate Discord application (own token, client ID and guild) | Does not reuse the production token or client ID |
| Uses a dedicated beta PostgreSQL, with its own volume and network | Does not mount production `.env`, volumes or networks |
| Registers the 25 slash commands **only** on the test guild | Does not publish the commands globally |
| Answers through the deterministic `stub` AI provider, with no network | Does not call OpenAI by default |
| Requires Internet: it talks to `discord.com` and to the real Gateway | Does not simulate Discord (the Spacebar beta exists for that) |

The beta bot **publishes no port**: the Gateway connection is outbound and the
`/health` and `/ready` probes are read from inside the stack.

## Prerequisites

- Windows 10/11 with Docker Desktop and the WSL2 backend enabled.
- Repository cloned and PowerShell opened in the **repository root** (the folder
  that contains `docker-compose.yml`): every command below assumes it.
- Stable Internet connection: without it the bot cannot reach Discord.
- A Discord account with access to the Discord Developer Portal.
- Little disk space: the images are the ones production already uses
  (`python:3.13-slim`, `postgres`), about 700 MB in total.

## Files involved

| File | Role |
|---|---|
| `docker-compose.discord-beta.yml` | Beta stack: `beta-bot`, `beta-postgres` |
| `.env.discord-beta.example` | Versioned template with the placeholders |
| `.env.discord-beta` | Real local configuration (**ignored by Git**) |
| `sakura-bot/tests/unit/test_discord_beta_configuration.py` | Tests that block isolation and sync regressions |

## Part 1 — Discord setup (manual, one time)

Everything in this part happens in the browser on the Discord Developer Portal
and in the Discord client. No script creates applications, tokens or guilds.

### 1.1 Create the beta application

1. Sign in to Discord in the browser with the account that will own the beta.
2. Open <https://discord.com/developers/applications>.
3. Click **New Application** (top right), name it `Sakura Spirit Bot (Beta)`,
   accept the developer terms and confirm with **Create**.
4. The beta is a **separate application**: same code, different identity. This is
   what makes a token leak or a mistake harmless for production.

### 1.2 Copy the Application ID

1. Left menu → **General Information**.
2. Row **Application ID** → **Copy**.

This value is the client ID the bot sends when it identifies itself, and it goes
into `SAKURA_BETA_DISCORD_CLIENT_ID`. It is a numeric string of 17-19 digits. Do
not confuse it with **Public Key** or **Application Secret**: this bot does not
use them.

### 1.3 Generate and copy the bot token

1. Left menu → **Bot**.
2. If no token is shown, click **Reset Token** → **Yes, do it!**. The token is
   displayed **once**: copy it immediately.
3. Paste it into `.env.discord-beta` on the `SAKURA_BETA_DISCORD_TOKEN=` line,
   with no quotes, no spaces and **no `Bot ` prefix** (the code adds it).
4. If you lose the token, **Reset Token** issues a new one and the old one stops
   working: update the file and restart the stack.

Never commit it, never paste it in a chat or a ticket, never include it in a
screenshot, never reuse the production token, never bake it into an image.

### 1.4 Enable the three privileged intents

Still on the **Bot** tab, section **Privileged Gateway Intents**:

| Toggle | Required | Why |
|---|---|---|
| **Presence Intent** | yes | `core/bot.py` requests `intents.presences` |
| **Server Members Intent** | yes | `core/bot.py` requests `intents.members` |
| **Message Content Intent** | yes | `core/bot.py` requests `intents.message_content` |

Click **Save Changes**. `intents.voice_states` is requested too, but it is not a
privileged intent and has no toggle.

Without these toggles the login fails with `PrivilegedIntentsRequired` (Gateway
close code `4014`, "Disallowed intent(s)"), even with a valid token. Under 100
guilds no bot verification is needed, so the toggles take effect immediately at
the next login.

### 1.5 Create the private test guild

1. In the Discord client, click **+** at the bottom of the server list.
2. **Create My Own** → **For me and my friends**.
3. Name it, for example `Sakura Beta Test`, and confirm.

Keep it private: no public discovery and no invites to strangers. Because the
sync is guild-scoped, the commands exist only in this guild.

### 1.6 Copy the guild ID

1. Enable Developer Mode: **User Settings** → **Advanced** → **Developer Mode**.
2. Right-click the server icon → **Copy Server ID**.
3. Paste it into `SAKURA_BETA_TEST_GUILD_ID` (17-19 digits).

Optional: right-click your own avatar → **Copy User ID** and put it in
`SAKURA_BETA_OWNER_ID`. The bot starts without it; the variable only marks the
owner account.

### 1.7 Invite the bot into the test guild

1. Left menu → **OAuth2** → **URL Generator**.
2. Scopes: **`bot`** and **`applications.commands`**. The second one is
   mandatory: without it the slash commands cannot be registered, and the bot
   looks online but no command appears.
3. Bot permissions (least privilege for this bot): **View Channels**,
   **Send Messages**, **Embed Links**, **Read Message History**,
   **Add Reactions**, **Use Application Commands**.
4. Copy the generated URL, open it in the browser, select the **test** guild and
   click **Authorize**.

The bot appears in the member list as offline until the stack is started. Three
admin commands are declared with `default_permissions(administrator=True)`: to
exercise them, grant **Administrator** in the test guild (acceptable there) or
verify only the denial path with a normal account.

### 1.8 Fill `.env.discord-beta`

```powershell
Copy-Item .env.discord-beta.example .env.discord-beta
notepad .env.discord-beta
```

| Variable | Where the value comes from | Format |
|---|---|---|
| `SAKURA_BETA_DISCORD_TOKEN` | Bot → **Reset Token** | three dot-separated parts |
| `SAKURA_BETA_DISCORD_CLIENT_ID` | General Information → **Application ID** | 17-19 digits |
| `SAKURA_BETA_TEST_GUILD_ID` | right-click the server → **Copy Server ID** | 17-19 digits |
| `SAKURA_BETA_OWNER_ID` | right-click your avatar → **Copy User ID** | optional, 17-19 digits |
| `SAKURA_BETA_POSTGRES_PASSWORD` | your choice | alphanumeric only |
| `SAKURA_BETA_AI_PROVIDER` | `stub` (default) or `openai` | `stub` needs no key |
| `SAKURA_BETA_OPENAI_API_KEY` | only for `openai` | dedicated beta key |

Every `INSERISCI_*` and `CAMBIA_*` placeholder must be replaced: the bot rejects
the template values before the login instead of connecting with fake
credentials. The database password must be alphanumeric, because it is embedded
in the SQLAlchemy URL without escaping (`@ : / #` would break it).

### 1.9 Token hygiene

- The beta application is disposable: **Reset Token** revokes access without
  touching production.
- If the token leaks, reset it, update `.env.discord-beta`, restart, then check
  the guild audit log for unexpected actions.
- `.env.discord-beta` is covered by `.gitignore`; never copy it into an image
  and never mount it in a stack other than the beta one.

## Part 2 — Local configuration

The file is created and filled in [1.8](#18-fill-envdiscord-beta). Validate it
without starting anything:

```powershell
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml config --quiet
```

An empty output and exit code `0` mean the file is complete: every required
variable is present (`:?` in the Compose file fails otherwise) and the
interpolation is valid. If a placeholder is still there the command still
succeeds, but the bot refuses to start: the settings validation runs before the
login and the process exits with an explicit error instead of connecting with
fake credentials.

## Part 3 — First start

```powershell
# Start ONLY the Discord beta.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml up -d --build

# Status of the two beta services.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml ps

# Beta bot log.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml logs -f beta-bot
```

`-f docker-compose.discord-beta.yml` and `--env-file .env.discord-beta` are
mandatory: a bare `docker compose up` starts the production stack with the
production `.env`.

Expected lines in the log, in this order:

```text
Loaded extension: commands.spirit_commands
...
Synced 25 slash commands
Sakura Spirit Bot is ready!
```

`Synced 25 slash commands` proves the guild-scoped upload: the commands are now
in the test guild only.

## Part 4 — Verification

```powershell
# Readiness from inside the container: no port is published on the host.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml exec -T beta-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready').read().decode())"
```

Expected answer, HTTP 200:

```json
{"status": "ready", "checks": {"discord": true, "bootstrap": true, "database": true, "cache": true, "extensions": true}}
```

- `/health` (HTTP 200) only proves the process is alive: it does **not** prove
  that Discord is connected.
- `/ready` requires a connected Gateway, a completed bootstrap, a reachable
  PostgreSQL, an initialised local cache and every required extension loaded. HTTP
  503 with a `false` check tells which part is missing.
- In the Discord client the `sakura-*` commands must appear **in the test guild
  only**. If they appear in other guilds the sync went global: stop the beta
  immediately and check `SAKURA_BOT_ENVIRONMENT` and
  `SAKURA_BOT_TEST_GUILD_ID`.

## Part 5 — Functional tests in the client

Run the commands in a channel of the test guild and record the outcome. The names
are the ones verified by `sakura-bot/tests/smoke/test_command_registry.py`.

| Area | Command | Minimum check | Result |
|---|---|---|---|
| Registry | `/sakura-help` | Command visible, help embed | TO RUN |
| User | `/sakura-profile` | Profile created/read in beta PostgreSQL | TO RUN |
| Guild | `/sakura-server-info` | Test guild name and ID, not production | TO RUN |
| Weather | `/sakura-weather` | State read and stored in the beta DB | TO RUN |
| Spirits | `/sakura-spirit-adopt` | Adoption embed, row in `user_spirits` | TO RUN |
| Spirits | `/sakura-my-spirit` | The adopted spirit is read back | TO RUN |
| AI stub | `/sakura-spirit-interact` | Deterministic answer, no network log | TO RUN |
| Social | `/sakura-daily-dream` | Dream embed, row in `daily_dreams` | TO RUN |
| Social | `/sakura-send-gift` | Correct defer/followup, currency moved | TO RUN |
| Gaming | `/sakura-lfg` | Session row in beta PostgreSQL, reactions handled | TO RUN |
| Permissions | `/sakura-admin-stats` | Denied to a non-admin user | TO RUN |
| Permissions | `/sakura-admin-set-weather` | Allowed to an admin user | TO RUN |
| Errors | Wrong parameters | Error message, no unhandled exception | TO RUN |
| Visual | Embeds in the beta channels | Optional manual screenshot (`Win + Shift + S`) | TO RUN |

The permission rows need **two normal human accounts**: one with administrator
permissions and one without. Never use user-account tokens or self-bots.

`gacha` and `events` are **not** loaded by the bootstrap: their commands do not
exist and must not be expected in this beta.

## Daily commands

```powershell
# Beta bot log.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml logs -f beta-bot

# Restart only the bot after a code change.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml up -d --build beta-bot

# Stop the beta keeping the data.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml down
```

## Reset of the beta environment only

Destructive: it deletes the beta data, never the production one. Run it only
after checking the project name.

```powershell
# The project name must be sakura-spirit-bot-discord-beta.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml ls

# Reset: containers and volumes of the beta project only.
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml down -v
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Replace the .env template placeholders before starting: ...` | A `INSERISCI_*` value is still in `.env.discord-beta` | Fill the listed variables and restart |
| `Invalid AI provider configuration` at startup | `SAKURA_BETA_AI_PROVIDER` is neither `stub` nor `openai` | Correct the value in the local file |
| `SAKURA_BOT_TEST_GUILD_ID is required` | `SAKURA_BOT_ENVIRONMENT=discord-beta` without a guild ID | Fill `SAKURA_BETA_TEST_GUILD_ID`; the bot stops instead of syncing globally |
| `PrivilegedIntentsRequired`, Gateway close code `4014` | One of the three privileged intents is off | Enable Presence, Server Members and Message Content, then restart |
| `Improper token has been passed` | Wrong, reset or production token | Copy the beta application token, no spaces, no `Bot ` prefix |
| Bot online but no command answers | Privileged intents off, or the app was invited without `applications.commands` | Enable the intents and re-invite with the correct scopes |
| Commands do not appear in the guild | Sync went to another guild, or a stale client cache | Check `SAKURA_BETA_TEST_GUILD_ID`, restart the bot, reopen the client |
| Commands appear in other guilds | The sync went global | Stop the beta and check `SAKURA_BOT_ENVIRONMENT` and `SAKURA_BOT_TEST_GUILD_ID` |
| `/ready` returns 503 with `database: false` | Beta PostgreSQL not ready or wrong password | Check `ps` and the `beta-postgres` log |
| `/ready` returns 503 with `cache: false` | The in-process cache was not initialised (bootstrap failure) | Check the `beta-bot` log for the bootstrap error |
| `/ready` returns 503 with `discord: false` | Gateway not connected (no network, wrong token) | Check connectivity and the bot log |
| `password authentication failed` on PostgreSQL | Password with special characters not encoded in the URL | Use an alphanumeric password and recreate the beta volume |

## Known limits of this guide

- The Discord application setup is manual: no script creates applications,
  tokens or guilds.
- The `stub` provider does not verify the quality of real AI answers: that needs
  `SAKURA_BETA_AI_PROVIDER=openai` with a dedicated beta key and an explicit
  authorization.
- Embed rendering must be judged by eye in the client: no automated test covers
  it.
- Isolation is guaranteed by a separate Compose project, volumes, networks and
  credentials; it is not a security boundary against an operator who copies the
  production token by hand.
- The online tests remain `NOT RUN` until the beta credentials are filled in and
  the authorization to connect to Discord is granted.
