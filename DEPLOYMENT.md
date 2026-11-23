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

3. **Redis Server**
   - Redis 6+ recommended
   - Used for caching and real-time data

4. **OpenAI API Key**
   - Sign up at [OpenAI](https://platform.openai.com/)
   - Create an API key with access to GPT models

5. **Server/VPS**
   - Ubuntu 22.04 LTS recommended
   - Minimum 2GB RAM, 1 CPU core
   - Python 3.11+ installed

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
SAKURA_BOT_REDIS_URL=redis://localhost:6379/0
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
| `sakura-redis` | `redis:${SAKURA_REDIS_VERSION}` | none | LFG sessions and cooldowns |
| `sakura-proxy` | `traefik:${SAKURA_PROXY_TRAEFIK_VERSION}` | `127.0.0.1:${SAKURA_PROXY_HTTPS_PORT}` | TLS termination for the health endpoint |
| `sakura-proxy-logrotate` | built from `sakura-proxy-logrotate/Dockerfile` | none | Log rotation for Traefik and bot logs |

Operational notes:

- `SAKURA_BOT_CACHE_REQUIRED=true` is set in `docker-compose.yml`: the bot refuses to
  start without Redis. Remove the `sakura-redis` service only after switching the
  variable to `false`, which enables the degraded cache mode reported by
  `/ready`.
- Every container writes its state to a named volume (`sakura-postgres-data`,
  `sakura-bot-logs`, `sakura-proxy-logs`, `sakura-proxy-logrotate-state`,
  `sakura-proxy-logrotate-logs`). The volumes survive image rebuilds and
  `docker compose down`; only `docker compose down -v` removes them. The bot
  image creates `/var/log/sakura-bot` as UID 10001, so a fresh volume inherits
  the right owner and no host-side `chown` is needed.
- Traefik has no default certificate configured, so it generates a self-signed one.
  Replace it with a real certificate before exposing the endpoint.
- The Traefik dashboard and ping endpoint are bound to the container loopback and
  are intentionally not published.
- Traefik routes only `Path(`/health`)`, published on the host loopback. `/ready`
  is not routed: read it inside the Docker network with
  `docker compose exec sakura-bot ...` (see the day-to-day commands below).
- The five `container_name` entries are fixed, so `docker compose -p <other>`
  alone does not isolate a second copy of this stack: remove or parameterise
  those names before running two stacks side by side.

Day-to-day commands:

```bash
docker compose logs -f sakura-bot
docker compose exec sakura-bot python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready').read().decode())"
curl -k https://localhost/health
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
After=network.target postgresql.service redis.service

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

With Compose the bot writes to the `sakura-bot-logs` volume and Traefik to
`sakura-proxy-logs`; the `sakura-proxy-logrotate` sidecar rotates both every 15
minutes. When the bot runs directly on the host instead, logs go to the path in
`SAKURA_BOT_LOG_FILE` (`logs/sakura_bot.log` by default) and need a host
logrotate rule:

```bash
# Create logrotate config
sudo nano /etc/logrotate.d/sakura-bot
```

Add:

```
/home/ubuntu/sakura-spirit-bot/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
}
```

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
- Redis cache hit rates
- Discord API rate limits

## Scaling Considerations

For larger deployments:

1. **Database Connection Pooling**: Already implemented via SQLAlchemy
2. **Redis Clustering**: For high-traffic servers
3. **Horizontal Scaling**: Run multiple bot instances with a shared database
4. **Load Balancing**: Distribute commands across instances

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
- Ensure Redis is running
- Check logs for error messages

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -U sakura_user -d sakura_bot -h localhost

# Check if database exists
psql -U postgres -c "\\l"
```

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping

# Check Redis status
sudo systemctl status redis
```

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
- [ ] Redis running and accessible
- [ ] Bot tested in a development server
- [ ] Logging configured
- [ ] Monitoring set up
- [ ] Backup strategy in place
- [ ] Security review completed
- [ ] Documentation reviewed
- [ ] Emergency procedures documented

---

**Happy Deploying! 🌸**
