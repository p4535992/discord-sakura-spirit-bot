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

- Python 3.11+
- PostgreSQL Server
- Redis Server
- Discord Bot Token
- OpenAI API Key

### 1. Clone the Repository

```bash
git clone <repository_url>
cd sakura-spirit-bot
```

### 2. Install Dependencies

Create a virtual environment and install the required packages:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the `.env.example` file to `.env` and fill in the required values:

```bash
cp .env.example .env
```

**Required values:**

- `DISCORD_TOKEN`: Your Discord bot token.
- `DISCORD_CLIENT_ID`: Your Discord bot's client ID.
- `DATABASE_URL`: Your PostgreSQL connection URL.
- `REDIS_URL`: Your Redis connection URL.
- `OPENAI_API_KEY`: Your OpenAI API key.
- `BOT_OWNER_ID`: Your Discord user ID.

### 4. Set Up the Database

Ensure your PostgreSQL server is running and the database specified in `DATABASE_URL` exists. The bot will automatically create the necessary tables on first run.

### 5. Run the Bot

```bash
python main.py
```

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
/sakura-bot
├── commands/         # Command cogs
├── core/             # Core bot logic, db, cache
├── models/           # SQLAlchemy models
├── systems/          # Feature systems (spirits, weather, etc.)
├── utils/            # Utility functions
├── migrations/       # Database migrations
├── tests/            # Pytest tests
├── assets/           # Static assets
├── .env.example      # Environment variable template
├── main.py           # Main entry point
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## 🤝 Contributing

Please see `CONTRIBUTING.md` for details on how to contribute to this project.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
