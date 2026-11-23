# sakura-redis

Redis container (`sakura-redis`), image `redis:${REDIS_VERSION}`.

- `config/redis.conf`: no persistence (`save ""`, `appendonly no`), listens on
  all interfaces inside the compose network and disables protected mode because
  the port is never published on the host.
- Used by `core/cache.py` for LFG sessions and cooldowns.
- No volume: the cache is ephemeral and is rebuilt after a restart.
- Removing the service requires `SAKURA_BOT_CACHE_REQUIRED=false`, which puts
  the bot in the explicit degraded cache mode reported by `/ready`.
