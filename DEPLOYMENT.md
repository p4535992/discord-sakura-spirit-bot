# 🚀 Sakura Spirit Bot - Deployment Guide

This guide provides comprehensive instructions for deploying the Sakura Spirit Bot to a production environment.

## Prerequisites

Before deploying the bot, ensure you have the following:

### Required Services

1. **Discord Bot Application**
   - Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
   - Enable the following intents: Server Members, Message Content, Presence
   - Copy the bot token

2. **PostgreSQL Database**
   - PostgreSQL 14+ recommended
   - Create a database for the bot
   - Also stores LFG sessions and ritual cooldowns: they are game state and must
     survive a restart

3. **OpenAI API Key**
   - Sign up at [OpenAI](https://platform.openai.com/)
   - Create an API key with access to GPT models

4. **Server/VPS**
   - Ubuntu 22.04 LTS recommended
   - Minimum 2GB RAM, 1 CPU core
   - Python 3.11+ installed

No Redis, proxy or log-rotation service is required: the cache is in-process,
the bot connects outbound to the Discord Gateway and it logs to stdout.

## Local Development Setup

### Step 1: Clone and Install

```bash
# Clone the repository
git clone <repository_url>
cd sakura-spirit-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r sakura-bot/requirements.txt
```

### Step 2: Configure Environment

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Bot container (SAKURA_BOT_ prefix)
SAKURA_BOT_DISCORD_TOKEN=your_bot_token_here
SAKURA_BOT_DISCORD_CLIENT_ID=your_client_id_here
SAKURA_BOT_OPENAI_API_KEY=your_openai_api_key_here
SAKURA_BOT_ENVIRONMENT=development
SAKURA_BOT_PREFIX=!
SAKURA_BOT_OWNER_ID=your_discord_user_id

# Bot URLs: docker compose builds them for the container, set them only when
# running main.py directly on the host.
SAKURA_BOT_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/sakura_bot
```

### Step 3: Set Up Database

Ensure PostgreSQL is running and create the database:

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE sakura_bot;

# Create user (optional)
CREATE USER sakura_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE sakura_bot TO sakura_user;
```

### Step 4: Run the Bot

```bash
python sakura-bot/main.py
```

The bot will automatically create all necessary database tables on first run.

## Production Deployment

### Option 1: Docker Compose (Recommended)

The repository ships the complete stack; no Dockerfile has to be written.

```bash
cp .env.example .env      # fill every CHANGE_ME value
docker compose up -d --build
docker compose ps
```

| Service | Image | Published port | Purpose |
|---|---|---|---|
| `sakura-bot` | built from `sakura-bot/Dockerfile` | none | Discord bot; health endpoint on 8080 inside the network |
| `sakura-postgres` | `postgres:${SAKURA_POSTGRES_VERSION}` | `127.0.0.1:${SAKURA_POSTGRES_PORT}` | Database, volume `sakura-postgres-data` |

Operational notes:

- Two containers only. The cache is in the bot process (`core/cache.py`) and LFG
  sessions and ritual cooldowns are rows in PostgreSQL, so no Redis service is
  started and no cache flag has to be configured.
- The bot connects **outbound** to the Discord Gateway: there is no inbound
  proxy, no Traefik and no published HTTPS endpoint. Both probes are read inside
  the container with `docker compose exec` (see the day-to-day commands below).
- PostgreSQL writes to the named volume `sakura-postgres-data`. The volume
  survives image rebuilds and `docker compose down`; only
  `docker compose down -v` removes it. The former `sakura-bot-logs`,
  `sakura-proxy-logs` and `sakura-proxy-logrotate-*` volumes are no longer
  declared: they are not deleted automatically, so the old files stay available
  until the operator removes them.
- The application logs to stdout/stderr and Docker rotates the output with the
  `json-file` driver (`max-size: "10M"`, `max-file: "3"`): a bound on disk usage,
  not on the memory of the container.
- The two `container_name` entries are fixed, so `docker compose -p <other>`
  alone does not isolate a second copy of this stack: remove or parameterise
  those names before running two stacks side by side.

Day-to-day commands:

```bash
docker compose logs -f sakura-bot
docker compose exec sakura-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())"
docker compose exec sakura-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready').read().decode())"
docker compose down          # keeps the named volumes
```

### Test Database Stack

The destructive PostgreSQL integration test needs its own cluster.
`docker-compose.test.yml` provides it: separate project name, separate network,
tmpfs storage, no container name and no access to `sakura-postgres-data`.

```bash
docker compose -f docker-compose.test.yml up -d --wait
export SAKURA_POSTGRES_TEST_DATABASE_URL=postgresql+asyncpg://sakura_test:sakura_test_pw@127.0.0.1:55432/sakura_test
cd sakura-bot && pytest -m integration
docker compose -f docker-compose.test.yml down
```

`tests/support/database_guard.py` validates the URL before any DDL and rejects
anything that is not a throwaway test database. Never run the integration suite
against `sakura-postgres`, and never use `docker compose down -v` on the
application project as a cleanup step.

### Option 2: Systemd Service

Create a systemd service file at `/etc/systemd/system/sakura-bot.service`:

```ini
[Unit]
Description=Sakura Spirit Bot
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/sakura-spirit-bot
Environment="PATH=/home/ubuntu/sakura-spirit-bot/venv/bin"
ExecStart=/home/ubuntu/sakura-spirit-bot/venv/bin/python sakura-bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable sakura-bot

# Start service
sudo systemctl start sakura-bot

# Check status
sudo systemctl status sakura-bot

# View logs
sudo journalctl -u sakura-bot -f
```

## Database Migrations

Alembic is declared in `requirements.txt` but migrations are not configured yet:
there is no `alembic.ini` and no `migrations/` directory. The schema is created
at startup by `Base.metadata.create_all`, which only adds missing tables and
never alters existing columns.

Until migrations are introduced, a schema change requires a manual plan, for
example a reviewed SQL script applied before deploying the new bot version.
Treat migration tooling as pending work rather than an available feature.

## Monitoring and Maintenance

### Logging

The bot writes every record to stdout/stderr: there is no log file, no log volume
and no logrotate sidecar. Under Compose, Docker captures the stream and rotates it
with the `json-file` driver (`max-size`/`max-file` in the Compose file):

```bash
docker compose logs -f sakura-bot
```

When the bot runs directly on the host, redirect the output of the process to the
supervisor of your choice (systemd sends it to the journal, readable with
`sudo journalctl -u sakura-bot -f`). Do not reintroduce an application log file:
it would bypass the rotation that Docker and the journal already provide.

### Backup Database

Regular backups are essential. With Compose the database lives in the
`sakura-postgres-data` volume, so dump it through the running container:

```bash
set -a; . ./.env; set +a          # SAKURA_POSTGRES_USER / SAKURA_POSTGRES_DB

# Backup PostgreSQL
docker compose exec -T sakura-postgres pg_dump -U "$SAKURA_POSTGRES_USER" "$SAKURA_POSTGRES_DB" > backup_$(date +%Y%m%d).sql

# Restore from backup
docker compose exec -T sakura-postgres psql -U "$SAKURA_POSTGRES_USER" "$SAKURA_POSTGRES_DB" < backup_20240101.sql
```

Keep the dumps outside the repository, on the disk that holds the backups.

### Performance Monitoring

Monitor bot performance:

- CPU and memory usage
- Database query performance
- Discord API rate limits
- `/ready` status and the `checks` block

## Scaling Considerations

For larger deployments:

1. **Database Connection Pooling**: Already implemented via SQLAlchemy
2. **Horizontal Scaling**: The cache is in-process, so it is not shared between
   replicas: run a single bot instance per token. Multiple instances would need a
   shared cache and a shared scheduler, which this project does not implement.
3. **Database size**: LFG sessions and ritual cooldowns are rows in PostgreSQL;
   expired LFG sessions can be purged with
   `core.lfg_repository.purge_expired_sessions` from a maintenance job.

## Security Best Practices

1. **Environment Variables**: Never commit `.env` files
2. **Database Security**: Use strong passwords and restrict access
3. **API Keys**: Rotate keys regularly
4. **Rate Limiting**: Respect Discord API limits (implemented)
5. **Input Validation**: All user inputs are validated

## Troubleshooting

### Bot Won't Start

- Check `.env` file is properly configured
- Verify database connection
- Check logs for error messages (`docker compose logs sakura-bot`)

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -U sakura_user -d sakura_bot -h localhost

# Check if database exists
psql -U postgres -c "\\l"
```

### Readiness Stays 503

`/ready` returns 503 until the Gateway is connected, the bootstrap is complete,
PostgreSQL answers a trivial query and every required extension is loaded. Read
the `checks` block to see which one is false:

```bash
docker compose exec sakura-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready').read().decode())"
```

### LFG or Ritual Cooldown Behave Unexpectedly

Both are rows in PostgreSQL (`lfg_sessions`, `lfg_members`,
`ritual_cooldowns`), not cache entries, so a restart no longer clears them. An
LFG post expires after one hour and every accepted join renews the window; the
ritual cooldown lasts 30 minutes per user. Inspect the rows with `psql` before
changing anything.

### Permission Issues

Ensure the bot has the following Discord permissions:

- Read Messages/View Channels
- Send Messages
- Embed Links
- Attach Files
- Add Reactions
- Use Slash Commands
- Manage Roles (for cosmetics)

## Updating the Bot

To update to a new version:

```bash
# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Update dependencies
pip install -r sakura-bot/requirements.txt --upgrade

# Restart the bot
sudo systemctl restart sakura-bot
```

## Support

For issues or questions:

- Check the logs first
- Review the documentation
- Open an issue on GitHub
- Contact the development team

## Production Checklist

Before going live:

- [ ] All environment variables configured
- [ ] Database properly set up and backed up
- [ ] `/ready` returns 200 with every check true
- [ ] Bot tested in a development server
- [ ] Logging visible through `docker compose logs` (or the journal)
- [ ] Monitoring set up
- [ ] Backup strategy in place
- [ ] Security review completed
- [ ] Documentation reviewed
- [ ] Emergency procedures documented

---

**Happy Deploying! 🌸**
