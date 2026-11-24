# 🌸 Sakura Spirit Bot

**Version: 1.0**

Welcome to the Sakura Spirit Bot, an immersive, interactive, and aesthetic bot that transforms your Discord server into a living, evolving world. This bot blends RPG mechanics, AI-driven systems, and social gamification into a cohesive Sakura-themed experience.

## ✨ Features

- **🌸 Spirit Ecosystem**: AI-driven spirits that roam the server, evolve, and interact with users.
- **🌤️ Dynamic Weather**: A weather system that impacts gameplay, spirit behavior, and server events.
- **💖 Social Engine**: Track relationships, emotional states, and receive personalized daily dreams.
- **🎮 Gaming Utilities**: LFG system, pre-game rituals, and game stat integration.
- **🗺️ Sakura Park**: A persistent virtual world to explore, with shops, NPCs, and mini-games.
- **🎰 Gacha System**: Pull for spirits, cosmetics, and items.
- **And much more!**

## 🚀 Getting Started

### Prerequisites

- Docker Desktop, or Docker Engine with Compose v2 (recommended path)
- Python 3.13 (manual path and test suite)
- Discord Bot Token and OpenAI API Key

### 1. Clone the Repository

```bash
git clone <repository_url>
cd discord-sakura-spirit-bot
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Replace every `CHANGE_ME` value in `.env`: `SAKURA_BOT_DISCORD_TOKEN`,
`SAKURA_BOT_DISCORD_CLIENT_ID`, `SAKURA_BOT_OPENAI_API_KEY` and
`SAKURA_POSTGRES_PASSWORD`. `SAKURA_BOT_OWNER_ID` is optional. Every key is
prefixed with the container that reads it (`SAKURA_BOT_*`,
`SAKURA_POSTGRES_*`), so the file stays grouped by service.
The password must be alphanumeric because it is embedded in
`SAKURA_BOT_DATABASE_URL` without escaping.

### 3. Start the Stack

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f sakura-bot
```

The stack runs two containers:

| Container | Role |
|---|---|
| `sakura-bot` | The bot itself (Python 3.13, unprivileged user) |
| `sakura-postgres` | PostgreSQL, data in the `sakura-postgres-data` volume |

The cache is in-process and LFG sessions and ritual cooldowns are stored in
PostgreSQL, so there is no Redis container. The bot connects **outbound** to the
Discord Gateway, so no inbound proxy is needed either: there is no Traefik and no
logrotate sidecar, and the application writes its logs to stdout/stderr.

PostgreSQL keeps its state in the `sakura-postgres-data` Docker named volume, so
rebuilding an image never touches data and no host directory has to be prepared.
`docker compose down` keeps the volume, `docker compose down -v` deletes it. The
former `sakura-bot-logs`, `sakura-proxy-logs` and `sakura-proxy-logrotate-*`
volumes are no longer declared and are **not** deleted automatically: the old
files stay available until the operator removes them.

Docker rotates the container logs through the `json-file` driver
(`max-size: "10M"`, `max-file: "3"`): that is a bound on disk usage, not on the
memory of the container.

Check the health endpoints:

```bash
docker compose exec sakura-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())"
docker compose exec sakura-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready').read().decode())"
```

`/health` reports process liveness. `/ready` reports whether the bot can serve
traffic (Discord gateway connected, bootstrap complete, PostgreSQL answering a
trivial query, local cache initialised, required extensions loaded): it returns
HTTP 503 with the failing checks. Neither probe is published on the host, so both
are read with `docker compose exec` as shown above. `checks.cache` describes the
in-process cache, not a remote service; `checks.database` is the check that
proves the persistent state is reachable.

### 4. Run Without Docker (optional)

```bash
cd sakura-bot
python3.13 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python main.py
```

With this path, uncomment `SAKURA_BOT_DATABASE_URL` in the repository root `.env`
and point it at a reachable PostgreSQL: the settings object also reads `../.env`,
so the same file serves Compose and a host run. No Redis is required: the cache
lives in the process and the LFG/cooldown state is in the same database.

### 5. Run the Tests

```bash
cd sakura-bot
pytest                    # smoke and unit tests, no external service needed
```

The PostgreSQL integration test drops and recreates the whole schema, so it runs
only against a throwaway database declared through
`SAKURA_POSTGRES_TEST_DATABASE_URL` and validated by
`tests/support/database_guard.py` before any DDL. The guard rejects a
non-PostgreSQL URL, an unknown host, a cluster maintenance database, a name
without the `test` token and any URL that resolves to the application database.
Without the variable the test is skipped; with the variable set an unreachable
server fails the run instead of reporting success.

The dedicated test database has its own compose file: own project name, own
network, tmpfs storage, no container name and nothing shared with the
application stack, so the `sakura-postgres-data` volume is never touched.

```bash
docker compose -f docker-compose.test.yml up -d --wait
export SAKURA_POSTGRES_TEST_DATABASE_URL=postgresql+asyncpg://sakura_test:sakura_test_pw@127.0.0.1:55432/sakura_test
cd sakura-bot && pytest -m integration
docker compose -f docker-compose.test.yml down
```

#### Full suite in Docker (integration included)

The host run above skips the PostgreSQL integration test when
`SAKURA_POSTGRES_TEST_DATABASE_URL` is not set. The isolated stack starts a
throwaway PostgreSQL, so the same suite runs complete and nothing is skipped:

```bash
docker compose --env-file .env.sakura-local-test -f docker-compose.sakura-local-test.yml up --build --abort-on-container-exit --exit-code-from sakura-test-runner sakura-test-runner
docker compose --env-file .env.sakura-local-test -f docker-compose.sakura-local-test.yml down
```

Result of the host run on this revision: **186 passed, 1 skipped**. The
integration test
`tests/integration/test_user_creation_postgres.py::test_user_and_stats_are_persisted`
runs against the throwaway cluster, after `tests/support/database_guard.py` has
verified the URL and the marker row; the host run skips it because that variable
is absent. The isolated stack above runs the same suite with the integration test
included.

#### Visual check of the running bot

The bot has no graphical interface: its observable surface is the HTTP probe
server. The screenshot below was captured with Playwright against the local
Spacebar stack, with the bot connected to the local Spacebar gateway and to its
own PostgreSQL. It is historical evidence of that run, not of the current
revision.

![Risposta di /ready del bot con tutti i controlli verdi](docs/images/spacebar-beta-ready.png)

*Risposta reale di `/ready`, letta dal browser e formattata per leggibilità.*

To reproduce it, start the stack and the evidence-only relay that publishes the
probe on the host loopback. The bot itself keeps no published port and no route
to the Internet: the relay forwards TCP to it from `127.0.0.1:3004`.

```bash
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml up -d
docker compose --env-file .env.spacebar -f docker-compose.spacebar.yml -f docker-compose.spacebar.evidence.yml up -d health-relay
# open http://127.0.0.1:3004/ready
```

The one-time Spacebar bootstrap is documented in `docs/SPACEBAR_BETA.md`; the
verified compatibility matrix, including what is still unverified, is in
`docs/SPACEBAR_COMPATIBILITY.md`.

#### Slash commands actually executed

A Discord client triggers a command by posting to `/interactions`. The script
`scripts/spacebar_invoke_command.py` sends the same request with a throwaway
local user, so the execution path can be verified without the web client:

```bash
.\.venv\Scripts\python.exe scripts\spacebar_invoke_command.py sakura-help --new-user
```

Verified result: **6 of the 25 registered commands executed**, each one replying
with its embed in `#general`; the bot log shows no `ERROR` or `Traceback` during
the five-command sequence.

| Command | Reply observed |
|---|---|
| `sakura-help` | `🌸 Sakura Spirit Bot - Help` |
| `sakura-server-info` | `🌸 Sakura Beta Guild` |
| `sakura-spirit-adopt` | `🎉 Spirit Companion Adopted!` |
| `sakura-my-spirit` | `🌸 Hanami` (state written by the previous command) |
| `sakura-spirit-interact` | spirit reply, with `POST /v1/chat/completions` 200 on the AI mock |
| `sakura-weather` | `🌤️ Weather Change: Gentle Breeze` |

The other 19 commands are registered but not executed: their status stays
`NOT_RUN` in `docs/SPACEBAR_COMPATIBILITY.md`.

#### Spacebar client UI screenshot (not yet captured)

**Status: NOT EXECUTED.** No screenshot of the Discord-like client interface
exists in this repository. Only the probe response above was captured.

The client is [Fermi](https://github.com/spacebarchat/client), a React 18 +
Vite 6 application. It is **not** distributed as a container image: the
following registries were checked and none of them publishes one.

```
ghcr.io/spacebarchat/client:latest         -> not found
ghcr.io/spacebarchat/web:latest            -> not found
ghcr.io/spacebarchat/spacebar-client:latest -> not found
spacebarchat/client:latest                 -> not found
```

It therefore has to be built from source, which requires `pnpm >= 9` and access
to the npm registry. The environment where the rest of this document was
verified blocks `registry.npmjs.org`, `codeload.github.com` and
`raw.githubusercontent.com` (connection timeouts), while `github.com` answers
only for git references, so `pnpm install` could not run there and the build was
not attempted.

To capture the screenshot on a machine with network access:

```bash
git clone --depth 1 https://github.com/spacebarchat/client.git
cd client
corepack enable && corepack prepare pnpm@9 --activate
pnpm install
# point the client at the local stack before building:
#   api     http://127.0.0.1:3002/api/v9
#   gateway ws://127.0.0.1:3001
#   cdn     http://127.0.0.1:3003
pnpm build
npx serve dist -l 8080
```

Then open `http://127.0.0.1:8080`, sign in with the local account created during
the bootstrap, open the guild that contains the bot and capture the screenshot.

Two points remain unverified and must be checked during that run:

- **where** the client reads its endpoints (a configuration module under `src/`
  or a `VITE_*` variable); the source was not readable from the restricted
  environment, so the exact override point is unknown;
- **CORS**: the client on `:8080` calls the API on `:3002`, which is a
  cross-origin request; if the API does not send `Access-Control-Allow-Origin`,
  both must be served from the same origin through a reverse proxy.

Until that run happens, the cases still listed as `NOT_RUN` in
`docs/SPACEBAR_COMPATIBILITY.md` (ephemeral responses, reaction events, voice,
and the graphical rendering of the embeds) stay unverified. Interaction
dispatch, initial-response embeds and the `defer()`/followup path are no longer
in that list: they were verified through `POST /interactions` and required four
adapter patches documented in the same file.

### 6. Discord Beta Stack (optional)

`docker-compose.discord-beta.yml` runs the same image against a **separate
Discord application** and a **private test guild**, with its own PostgreSQL,
volumes and networks. Nothing is shared with the production stack, and the slash
commands are registered on the test guild only. Two containers
(`beta-postgres`, `beta-bot`): the cache is in-process, as in production.

```bash
cp .env.discord-beta.example .env.discord-beta      # Windows: Copy-Item
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml config --quiet
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml up -d --build
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml exec -T beta-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready').read().decode())"
docker compose --env-file .env.discord-beta -f docker-compose.discord-beta.yml down
```

| Setting | Effect |
|---|---|
| `SAKURA_BOT_ENVIRONMENT=discord-beta` | Slash commands are synced to `SAKURA_BOT_TEST_GUILD_ID` instead of globally; without the guild ID the startup fails instead of publishing globally |
| `SAKURA_BOT_AI_PROVIDER=stub` | Deterministic answers computed in-process: no OpenAI client, no network call, no credit |
| `SAKURA_BOT_AI_PROVIDER=openai` | Production behaviour, allowed only with a dedicated beta key |

The bot publishes no port: the Gateway connection is outbound and `/ready` is
read with `docker compose exec`, as shown above. `-f` and `--env-file` are
mandatory, because a bare `docker compose up` starts the production stack.

The manual Discord setup (new application, token, privileged intents, private
guild, invite scopes) and the full PowerShell walkthrough are in
`docs/DISCORD_BETA_GUIDE_WINDOWS.md`; the Italian translation is
`docs/DISCORD_BETA_GUIDE_WINDOWS_it.md`. The online verification is **NOT
EXECUTED**: it needs a beta token and an explicit authorization to reach
Discord.

Neither stack is the first step: to exercise the real bot code without any
Discord account, token or Internet access, run the self-hosted Spacebar beta
(`docker-compose.spacebar.yml`, guide in `docs/SPACEBAR_BETA.md`). The four test
levels are summarised at the top of `docs/DISCORD_BETA_GUIDE_WINDOWS.md`.

## 🤖 Usage

Once the bot is running and has joined your server, you can use the slash commands to interact with it. Start with `/sakura-help` to see a full list of commands.

### Core Commands

- `/sakura-help`: Displays the help message.
- `/sakura-profile`: View your user profile.
- `/sakura-server-info`: View information about the server.

### Spirit Commands

- `/sakura-my-spirit`: View your companion spirit.
- `/sakura-spirit-adopt`: Adopt a new spirit companion.
- `/sakura-spirit-interact`: Interact with your spirit.

### Weather Commands

- `/sakura-weather`: Check the current server weather.
- `/sakura-weather-effects`: View detailed weather effects.

...and many more! Explore the bot's commands to discover all the features.

## 🔧 Development

This bot is built with a modular architecture, making it easy to extend and add new features. The whole application lives in `sakura-bot/`: the core logic is in `sakura-bot/systems/` and the cogs are in `sakura-bot/commands/`.

### Project Structure

```
/discord-sakura-spirit-bot
├── sakura-bot/              # Bot container: build context and application code
│   ├── main.py              # Entry point
│   ├── core/                # Bootstrap, config, database, cache, health endpoint
│   ├── commands/            # Command cogs
│   ├── models/              # SQLAlchemy models
│   ├── systems/             # Feature systems (spirits, weather)
│   ├── utils/               # Embed helpers
│   ├── tests/               # Pytest smoke, unit and integration tests
│   ├── Dockerfile           # Multi-stage image build
│   ├── .dockerignore        # Build-context exclusions
│   ├── requirements.txt     # Runtime dependencies
│   ├── requirements-dev.txt # Test and quality dependencies
│   ├── pyproject.toml       # Pytest and black configuration
│   └── .flake8              # Lint configuration
├── sakura-postgres/         # PostgreSQL container notes (env-only configuration)
├── sakura-redis/            # Historical: Redis container, no longer part of the stack
├── sakura-proxy/            # Historical: Traefik container, no longer part of the stack
├── sakura-proxy-logrotate/  # Historical: logrotate sidecar, no longer part of the stack
├── .env.example             # Environment variable template
├── .env.discord-beta.example # Discord beta template (separate app and guild)
├── docker-compose.yml       # Bot and PostgreSQL
├── docker-compose.discord-beta.yml # Discord beta: separate app, own DB and volumes
├── docker-compose.test.yml  # Throwaway PostgreSQL for the integration tests
├── docker-compose.sakura-local-test.yml # Full suite on throwaway services
├── docker-compose.spacebar.yml # Local Spacebar beta stack
├── docs/                    # Beta guides and Spacebar compatibility matrix
└── README.md                # This file
```

Each container has its own folder named after it (`sakura-bot/`,
`sakura-postgres/`, ...) holding its `config/`, `scripts/`, `Dockerfile` and a
short `README.md`. Folder name, compose service name, `container_name` and
environment prefix always match, so `sakura-postgres` is the `sakura-postgres/`
folder, the `sakura-postgres` service and the `SAKURA_POSTGRES_*` variables.
`sakura-redis/`, `sakura-proxy/` and `sakura-proxy-logrotate/` are kept only as
historical material for rollback: no active Compose file references them.
`sakura-bot/` also holds the whole application (sources, tests, requirements and
lint configuration), so it is the build context of the bot image; the repository
root keeps only the project-level files (Compose, `.env.example`,
documentation).

## 🤝 Contributing

Keep the existing module layout, add tests under `sakura-bot/tests/` and run
`pytest` from `sakura-bot/` before opening a change request.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
