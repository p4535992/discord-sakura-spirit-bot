# sakura-bot

Discord application container (`sakura-bot`). This folder is self-contained: it
holds the whole application and is the image build context.

## Contents

- `main.py`: entry point (logging setup, `asyncio.run`).
- `core/`: bootstrap, settings, database, cache, health endpoint, services.
- `commands/`: one cog per feature area, slash commands only.
- `models/`: SQLAlchemy 2.0 models.
- `systems/`: spirit AI and weather engine.
- `utils/`: embed helpers.
- `tests/`: pytest smoke, unit and integration tests (excluded from the image).
- `requirements.txt` / `requirements-dev.txt`: runtime and test dependencies.
- `pyproject.toml` / `.flake8`: pytest, black and flake8 configuration.
- `Dockerfile` / `.dockerignore`: multi-stage build on `python:3.13-slim`,
  runtime user UID 10001, healthcheck against `http://127.0.0.1:8080/health`.

## Build and test

```bash
docker build -t sakura-spirit-bot:local .    # build context is this folder
pytest                                       # no external service needed
```

The PostgreSQL integration test drops and recreates the whole schema. It runs
only against a throwaway database declared through
`SAKURA_POSTGRES_TEST_DATABASE_URL`, validated by
`tests/support/database_guard.py` before any DDL (PostgreSQL + asyncpg, allowed
host, name carrying the `test` token, not the application database). Without the
variable the test is skipped; with the variable set an unreachable server fails
the run. The dedicated cluster comes from `../docker-compose.test.yml`.

- Configuration: environment variables only, all prefixed `SAKURA_BOT_`
  (see `../.env.example`). For a host run the settings object also reads
  `../.env`, so the root file works without copying it into this folder.
- Logs: the named volume `sakura-bot-logs` is mounted on `/var/log/sakura-bot`
  and rotated by the `sakura-proxy-logrotate` sidecar.
- The image runs unprivileged (UID 10001) and creates `/var/log/sakura-bot` with
  that owner, so a fresh named volume inherits the correct permissions without
  any host-side `chown`.
