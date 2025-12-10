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
pip install -r requirements.txt
```

### Step 2: Configure Environment

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Discord Configuration
DISCORD_TOKEN=your_bot_token_here
DISCORD_CLIENT_ID=your_client_id_here

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/sakura_bot

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Environment
ENVIRONMENT=development

# Bot Configuration
BOT_PREFIX=!
BOT_OWNER_ID=your_discord_user_id
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
python main.py
```

The bot will automatically create all necessary database tables on first run.

## Production Deployment

### Option 1: Docker Deployment (Recommended)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    postgresql-client \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Run the bot
CMD ["python", "main.py"]
```

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  bot:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs

  postgres:
    image: postgres:14-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: sakura_bot
      POSTGRES_USER: sakura_user
      POSTGRES_PASSWORD: your_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

Deploy with Docker:

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f bot

# Stop
docker-compose down
```

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
ExecStart=/home/ubuntu/sakura-spirit-bot/venv/bin/python main.py
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

When updating the bot with schema changes, you may need to run migrations. Currently, the bot uses automatic table creation, but for production, consider using Alembic:

```bash
# Initialize Alembic (first time only)
alembic init migrations

# Create a migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head
```

## Monitoring and Maintenance

### Logging

Logs are stored in the `logs/` directory. Configure log rotation:

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

Regular backups are essential:

```bash
# Backup PostgreSQL
pg_dump -U sakura_user sakura_bot > backup_$(date +%Y%m%d).sql

# Restore from backup
psql -U sakura_user sakura_bot < backup_20240101.sql
```

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
pip install -r requirements.txt --upgrade

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
