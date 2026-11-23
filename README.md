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

Replace every `CHANGE_ME` value in `.env`: `DISCORD_TOKEN`, `DISCORD_CLIENT_ID`,
`OPENAI_API_KEY` and `POSTGRES_PASSWORD`. `BOT_OWNER_ID` is optional.
The password must be alphanumeric because it is embedded in `DATABASE_URL`
without escaping.

### 3. Start the Stack

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

The stack runs the two application containers and the supporting services the
code requires:

| Container | Role |
|---|---|
| `sakura-bot` | The bot itself (Python 3.13, unprivileged user) |
| `sakura-postgres` | PostgreSQL, data in `data/postgres` |
| `sakura-redis` | Redis for LFG sessions and cooldowns |
| `sakura-proxy` | Traefik on `https://localhost` with a self-signed certificate |
| `sakura-proxy-logrotate` | Log rotation sidecar for Traefik and bot logs |

Check the health endpoints:

```bash
curl -k https://localhost/health
docker compose exec bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready').read().decode())"
```

`/health` reports process liveness; `/ready` returns HTTP 503 with the failing
checks until PostgreSQL, Redis and the command extensions are available.

### 4. Run Without Docker (optional)

```bash
python3.13 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python main.py
```

With this path, uncomment `DATABASE_URL` and `REDIS_URL` in `.env` and point
them at reachable services.

### 5. Run the Tests

```bash
pytest                    # smoke and unit tests, no external service needed
pytest -m integration     # requires SAKURA_TEST_DATABASE_URL
```

The integration fixture drops and recreates the schema, so
`SAKURA_TEST_DATABASE_URL` must reference a throwaway database.

## 🤖 Usage

Once the bot is running and has joined your server, you can use the slash commands to interact with it. Start with `/sakura-help` to see a full list of commands.

### Core Commands

- `/sakura-help`: Displays the help message.
- `/profile`: View your user profile.
- `/server-info`: View information about the server.

### Spirit Commands

- `/my-spirit`: View your companion spirit.
- `/spirit-adopt`: Adopt a new spirit companion.
- `/spirit-interact`: Interact with your spirit.

### Weather Commands

- `/weather`: Check the current server weather.
- `/weather-effects`: View detailed weather effects.

...and many more! Explore the bot's commands to discover all the features.

## 🔧 Development

This bot is built with a modular architecture, making it easy to extend and add new features. The core logic is located in the `systems/` directory, and commands are in the `commands/` directory.

### Project Structure

```
/discord-sakura-spirit-bot
├── commands/             # Command cogs
├── core/                 # Bot bootstrap, config, database, cache, health endpoint
├── models/               # SQLAlchemy models
├── systems/              # Feature systems (spirits, weather)
├── utils/                # Embed helpers
├── tests/                # Pytest smoke, unit and integration tests
├── proxy/                # Traefik static and dynamic configuration
├── proxy-logrotate/      # Log rotation sidecar
├── data/                 # Local stack state, created at runtime (gitignored)
├── logs/                 # Runtime logs (gitignored)
├── .env.example          # Environment variable template
├── Dockerfile            # Bot image, multi-stage, non-root
├── docker-compose.yml    # Bot, PostgreSQL, Redis, Traefik, logrotate
├── main.py               # Main entry point
├── requirements.txt      # Runtime dependencies
├── requirements-dev.txt  # Test and quality dependencies
└── README.md             # This file
```

## 🤝 Contributing

Keep the existing module layout, add tests under `tests/` and run `pytest`
before opening a change request.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
