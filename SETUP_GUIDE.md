# 🌸 Sakura Spirit Bot - Complete Setup Guide

Welcome to the Sakura Spirit Bot! This guide will walk you through everything you need to know to get your bot up and running.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Discord Bot Setup](#discord-bot-setup)
4. [Local Installation](#local-installation)
5. [Configuration](#configuration)
6. [First Run](#first-run)
7. [Command Reference](#command-reference)
8. [Feature Configuration](#feature-configuration)
9. [Troubleshooting](#troubleshooting)

## Overview

The Sakura Spirit Bot is a comprehensive Discord bot that brings an immersive, Sakura-themed RPG experience to your server. It features AI-driven spirits, dynamic weather systems, social mechanics, gaming utilities, and much more.

### Key Features

**Spirit System**: AI-powered spirits that interact with users, evolve, and form bonds. Each spirit has unique personalities, factions, and abilities.

**Weather System**: Twelve distinct weather types that affect gameplay, including XP multipliers, gacha luck, and spirit activity levels.

**Social Features**: Track relationships between users, send gifts, receive daily dreams, and build emotional connections within your community.

**Gaming Utilities**: LFG (Looking for Group) system with automatic team formation, pre-game ritual buffs, and game statistics tracking.

**World Exploration**: Explore Sakura Park with eight unique zones, NPCs, shops, quests, and hidden secrets to discover.

**Gacha System**: Pull for spirits, cosmetics, badges, and items with rarity-based drop rates influenced by weather and emotional states.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

### Required Software

**Python 3.11 or higher**: The bot is built with Python and requires version 3.11+. You can download it from [python.org](https://www.python.org/downloads/).

**PostgreSQL 14+**: A relational database for persistent storage, including LFG
sessions and ritual cooldowns. Download from
[postgresql.org](https://www.postgresql.org/download/).

**Git**: For cloning the repository. Download from [git-scm.com](https://git-scm.com/downloads).

No Redis is needed: the cache lives inside the bot process.

### Required Accounts

**Discord Developer Account**: You'll need a Discord account to create a bot application at the [Discord Developer Portal](https://discord.com/developers/applications).

**OpenAI Account**: Required for AI-powered spirit interactions. Sign up at [platform.openai.com](https://platform.openai.com/).

## Discord Bot Setup

### Step 1: Create a Bot Application

Navigate to the Discord Developer Portal and create a new application. Give it a name like "Sakura Spirit Bot" and click Create.

### Step 2: Configure Bot Settings

Go to the Bot section and click "Add Bot". Customize your bot's username and avatar with Sakura-themed imagery.

### Step 3: Enable Intents

In the Bot section, scroll down to "Privileged Gateway Intents" and enable the following:

- **Presence Intent**: Required for tracking user activity
- **Server Members Intent**: Required for member management
- **Message Content Intent**: Required for reading messages

### Step 4: Get Your Bot Token

Click "Reset Token" to generate a new token. **Copy this token immediately** and store it securely. You'll need it for configuration.

### Step 5: Set Bot Permissions

Go to the OAuth2 section, then URL Generator. Select the following scopes:

- `bot`
- `applications.commands`

Then select these bot permissions:

- Read Messages/View Channels
- Send Messages
- Embed Links
- Attach Files
- Add Reactions
- Use Slash Commands
- Manage Roles

### Step 6: Invite Bot to Your Server

Copy the generated URL and paste it into your browser. Select your server and authorize the bot.

## Local Installation

### Step 1: Clone the Repository

Open your terminal and run:

```bash
git clone <repository_url>
cd sakura-spirit-bot
```

### Step 2: Create Virtual Environment

Create and activate a Python virtual environment:

```bash
# On Linux/Mac
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\\Scripts\\activate
```

### Step 3: Install Dependencies

Install all required Python packages:

```bash
pip install -r sakura-bot/requirements.txt
```

This will install discord.py, SQLAlchemy, the OpenAI client and the other
dependencies. No Redis client is installed: the cache is in-process.

### Step 4: Set Up PostgreSQL

Start PostgreSQL and create a database:

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE sakura_bot;

# Create user (optional but recommended)
CREATE USER sakura_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE sakura_bot TO sakura_user;

# Exit
\\q
```

### Step 5: Nothing Else to Start

The cache is in-process and LFG sessions and ritual cooldowns are tables in the
PostgreSQL database created above, so there is no Redis server, no proxy and no
log-rotation service to install or start.

## Configuration

### Step 1: Create Environment File

Copy the example environment file:

```bash
cp .env.example .env
```

### Step 2: Configure Environment Variables

Open `.env` in your text editor and fill in the following values:

```env
# Bot container
SAKURA_BOT_DISCORD_TOKEN=your_bot_token_from_discord_developer_portal
SAKURA_BOT_DISCORD_CLIENT_ID=your_bot_client_id_from_discord_developer_portal
SAKURA_BOT_PREFIX=!
SAKURA_BOT_OWNER_ID=your_discord_user_id
SAKURA_BOT_OPENAI_API_KEY=your_openai_api_key
SAKURA_BOT_ENVIRONMENT=development
SAKURA_BOT_LOG_LEVEL=INFO

# Bot URLs: docker compose builds them for the container, set them only when
# running main.py directly on the host.
SAKURA_BOT_DATABASE_URL=postgresql+asyncpg://sakura_user:your_secure_password@localhost:5432/sakura_bot

# Feature Flags (all enabled by default)
SAKURA_BOT_ENABLE_SPIRITS=true
SAKURA_BOT_ENABLE_WEATHER=true
SAKURA_BOT_ENABLE_SOCIAL=true
SAKURA_BOT_ENABLE_GAMING=true
SAKURA_BOT_ENABLE_WORLD=true
SAKURA_BOT_ENABLE_GACHA=true
SAKURA_BOT_ENABLE_EVENTS=true
```

### Step 3: Get Your Discord User ID

To get your Discord user ID:

1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click your username and select "Copy ID"
3. Paste this ID into `SAKURA_BOT_OWNER_ID` in your `.env` file

## First Run

### Step 1: No Log Directory Needed

The bot writes to stdout/stderr: there is no log file and no directory to
create. Under Docker the output is captured by `docker compose logs`; on a host
run it appears in the terminal (or in the journal when started by systemd).

### Step 2: Start the Bot

```bash
python sakura-bot/main.py
```

You should see output similar to:

```
============================================================
🌸 Starting Sakura Spirit Bot 🌸
============================================================
INFO     core.database Database connection established
INFO     core.cache Local TTL cache initialised (max 2048 entries)
INFO     core.bot Loaded extension: commands.spirit_commands
INFO     core.bot Loaded extension: commands.weather_commands
...
INFO     core.bot Logged in as SakuraSpirit#1234 (ID: 123456789)
INFO     core.bot Connected to 1 guilds
INFO     core.bot Sakura Spirit Bot is ready!
```

### Step 3: Test the Bot

In your Discord server, try these commands:

- `/sakura-help` - View all available commands
- `/sakura-profile` - View your profile
- `/sakura-server-info` - View server information
- `/sakura-spirit-adopt` - Adopt your first spirit companion

## Command Reference

### Core Commands

**`/sakura-help`**: Display comprehensive help information with all available commands organized by category.

**`/sakura-profile`**: View your personal profile including level, XP, currency, emotional state, and aura.

**`/sakura-server-info`**: Display server information including harmony score, current weather, and dominant faction.

### Spirit Commands

**`/sakura-my-spirit`**: View your companion spirit's details including power level, bond level, and evolution stage.

**`/sakura-spirit-adopt`**: Adopt a new spirit companion. You can only have one active companion at a time.

**`/sakura-spirit-interact <message>`**: Talk to your spirit and receive AI-generated responses based on their personality.

**`/sakura-spirit-info`**: Learn about the spirit system, factions, and rarity levels.

### Weather Commands

**`/sakura-weather`**: Check the current server weather and its effects on gameplay.

**`/sakura-weather-effects`**: View detailed breakdown of current weather effects including XP multipliers and bonuses.

**`/sakura-weather-history`**: See recent weather changes in the server.

**`/sakura-weather-list`**: Browse all possible weather types organized by rarity.

### Social Commands

**`/sakura-send-gift <user> [gift_type]`**: Send a gift to another user. Costs 50 currency, recipient receives 30 currency.

**`/sakura-daily-dream`**: View your personalized daily dream with potential buffs and effects.

**`/sakura-relationships`**: View your relationships with other users including warmth, rivalry, synergy, and chaos scores.

### Gaming Commands

**`/sakura-lfg <game> [party_size] [message]`**: Create a Looking for Group post. Others can react to join your party.

**`/sakura-ritual-buff [ritual_type]`**: Perform a pre-game ritual for temporary buffs. Types: victory, focus, teamwork, luck.

**`/sakura-game-stats`**: View your gaming statistics including games played and LFG sessions.

### World Commands

**`/sakura-explore [destination]`**: Explore different zones in Sakura Park. Start at "entrance" and discover connected areas.

**`/sakura-map`**: View the complete Sakura Park map with all zones and connections.

**`/sakura-shop`**: Visit the Spirit Shop to browse and purchase items.

**`/sakura-quests`**: View available quests with rewards and difficulty levels.

**`/sakura-inventory`**: View your inventory of items, cosmetics, and collectibles.

### Gacha Commands

**`/sakura-gacha-pull`**: Pull from the gacha for a chance to win spirits, cosmetics, or items. Costs 100 currency per pull.

### Admin Commands (Administrators Only)

**`/sakura-admin-toggle-feature <feature> <enabled>`**: Enable or disable specific bot features for your server.

**`/sakura-admin-set-weather <weather>`**: Manually change the server weather.

**`/sakura-admin-stats`**: View bot statistics including server count, user count, and latency.

## Feature Configuration

### Enabling/Disabling Features

Server administrators can control which features are active using the `/sakura-admin-toggle-feature` command:

```
/sakura-admin-toggle-feature feature:spirits enabled:true
```

Available features:
- `spirits` - Spirit system and companions
- `weather` - Dynamic weather system
- `social` - Social features and relationships
- `gaming` - LFG and gaming utilities
- `world` - Sakura Park exploration
- `gacha` - Gacha system
- `events` - Server-wide events

### Customizing Bot Behavior

You can customize bot behavior by editing the `core/config.py` file. Key settings include:

- XP gain rates
- Gacha rarity rates
- Weather change intervals
- Currency costs
- Spirit roaming frequency

## Troubleshooting

### Bot Won't Start

**Problem**: Bot fails to start or crashes immediately.

**Solutions**:
- Verify all environment variables in `.env` are correct
- Check that PostgreSQL is running
- Review the console output (or `docker compose logs sakura-bot`) for error messages
- Ensure Python version is 3.11 or higher

### Database Connection Error

**Problem**: "Failed to connect to database" error.

**Solutions**:
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Test database connection: `psql -U sakura_user -d sakura_bot`
- Check `SAKURA_BOT_DATABASE_URL` format in `.env`
- Ensure database exists and user has proper permissions

### LFG or Ritual Cooldown Look Stuck

**Problem**: an LFG post no longer accepts joins, or a ritual is refused.

**Solutions**:
- Both are rows in PostgreSQL (`lfg_sessions`, `lfg_members`,
  `ritual_cooldowns`): a restart does not clear them
- An LFG post expires after one hour and every accepted join renews the window;
  a full group rejects new members
- The ritual cooldown lasts 30 minutes per user, across all guilds
- Inspect the rows with `psql` before changing anything

### Commands Not Appearing

**Problem**: Slash commands don't show up in Discord.

**Solutions**:
- Wait a few minutes for Discord to sync commands
- Check bot has "applications.commands" scope
- Verify bot has proper permissions in the server
- Try kicking and re-inviting the bot

### OpenAI API Errors

**Problem**: Spirit interactions fail or return errors.

**Solutions**:
- Verify `SAKURA_BOT_OPENAI_API_KEY` is valid
- Check OpenAI account has available credits
- Review API rate limits
- Check logs for specific error messages

### Permission Errors

**Problem**: Bot can't perform certain actions.

**Solutions**:
- Verify bot role is high enough in role hierarchy
- Check bot has all required permissions
- Ensure bot can see and send messages in channels
- Review Discord audit log for permission denials

## Getting Help

If you encounter issues not covered in this guide:

1. Check the logs in `logs/sakura_bot.log`
2. Review the `ARCHITECTURE.md` file for technical details
3. Consult the `DEPLOYMENT.md` file for production setup
4. Open an issue on GitHub with detailed error information

## Next Steps

Now that your bot is running:

1. Customize the bot's personality and responses
2. Add custom spirits to the database
3. Create server-specific quests and events
4. Set up automated weather changes
5. Configure scheduled tasks
6. Explore advanced features in the documentation

**Enjoy your Sakura Spirit Bot! 🌸**
