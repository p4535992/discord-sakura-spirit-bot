# bot

Discord application container (`sakura-bot`).

- `Dockerfile`: multi-stage build on `python:3.13-slim`, runtime user UID 10001,
  healthcheck against `http://127.0.0.1:8080/health`.
- Build context is the repository root, because the image needs `main.py`,
  `core/`, `commands/`, `models/`, `systems/` and `utils/`:

  ```bash
  docker build -f bot/Dockerfile -t sakura-spirit-bot:local .
  ```

- Configuration: environment variables only, all prefixed `SAKURA_BOT_`
  (see `../.env.example`). No configuration file is mounted into the container.
- Logs: `../logs/bot` is mounted on `/var/log/sakura-bot` and rotated by the
  `proxy-logrotate` sidecar.
- The image runs unprivileged, so on a Linux host create the log directory with
  the matching owner first: `mkdir -p logs/bot && sudo chown 10001:10001 logs/bot`.
