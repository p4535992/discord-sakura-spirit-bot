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
`SAKURA_POSTGRES_*`, `SAKURA_REDIS_*`, `SAKURA_PROXY_*`,
`SAKURA_PROXY_LOGROTATE_*`), so the file stays grouped by service.
The password must be alphanumeric because it is embedded in
`SAKURA_BOT_DATABASE_URL` without escaping.

### 3. Start the Stack

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f sakura-bot
```

The stack runs the two application containers and the supporting services the
code requires:

| Container | Role |
|---|---|
| `sakura-bot` | The bot itself (Python 3.13, unprivileged user) |
| `sakura-postgres` | PostgreSQL, data in the `sakura-postgres-data` volume |
| `sakura-redis` | Redis for LFG sessions and cooldowns |
| `sakura-proxy` | Traefik on `https://localhost` with a self-signed certificate |
| `sakura-proxy-logrotate` | Log rotation sidecar for Traefik and bot logs |

Every container keeps its state in a Docker named volume of its own
(`sakura-postgres-data`, `sakura-bot-logs`, `sakura-proxy-logs`,
`sakura-proxy-logrotate-state`, `sakura-proxy-logrotate-logs`), so rebuilding an
image never touches data and no host directory has to be prepared. The
logrotate sidecar also mounts the bot and Traefik log volumes, because it
rotates those files in place. `docker compose down` keeps the volumes,
`docker compose down -v` deletes them.

Check the health endpoints:

```bash
curl -k https://localhost/health
docker compose exec sakura-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready').read().decode())"
```

`/health` reports process liveness and is the only path Traefik publishes, on
`127.0.0.1` only. `/ready` reports whether the bot can serve traffic (Discord
gateway connected, bootstrap complete, PostgreSQL reachable, Redis answering
`PING` when `SAKURA_BOT_CACHE_REQUIRED=true`, required extensions loaded): it
returns HTTP 503 with the failing checks and stays reachable only inside the
Docker network, so it is read with `docker compose exec` as shown above.

### 4. Run Without Docker (optional)

```bash
cd sakura-bot
python3.13 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python main.py
```

With this path, uncomment `SAKURA_BOT_DATABASE_URL` and `SAKURA_BOT_REDIS_URL`
in the repository root `.env` and point them at reachable services: the settings
object also reads `../.env`, so the same file serves Compose and a host run.

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
├── sakura-redis/            # Redis container: config/redis.conf
├── sakura-proxy/            # Traefik container: static and dynamic configuration
├── sakura-proxy-logrotate/  # Log rotation sidecar: Dockerfile, config, scripts
├── .env.example             # Environment variable template
├── docker-compose.yml       # Bot, PostgreSQL, Redis, Traefik, logrotate
├── docker-compose.test.yml  # Throwaway PostgreSQL for the integration tests
└── README.md                # This file
```

Each container has its own folder named after it (`sakura-bot/`,
`sakura-redis/`, ...) holding its `config/`, `scripts/`, `Dockerfile` and a
short `README.md`. Folder name, compose service name, `container_name` and
environment prefix always match, so `sakura-proxy` is the `sakura-proxy/`
folder, the `sakura-proxy` service and the `SAKURA_PROXY_*` variables. `sakura-bot/`
also holds the whole application (sources, tests, requirements and lint
configuration), so it is the build context of the bot image; the repository root
keeps only the project-level files (Compose, `.env.example`, documentation).

## 🤝 Contributing

Keep the existing module layout, add tests under `sakura-bot/tests/` and run
`pytest` from `sakura-bot/` before opening a change request.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
