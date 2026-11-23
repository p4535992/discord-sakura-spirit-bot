# sakura-proxy-logrotate

Log rotation sidecar (`sakura-proxy-logrotate`), built from `Dockerfile` on
`alpine:3.24.4`.

- `config/crontab`: runs the rotation every 15 minutes.
- `config/logrotate.conf`: `copytruncate` for the Traefik and bot logs, so the
  writing processes never need a restart.
- `scripts/start.sh`: entrypoint (cron in the foreground).
- `scripts/rotate_once.sh`: manual rotation, useful for verification.
- `scripts/healthcheck.sh`: container healthcheck.
- State: `../data/sakura-proxy-logrotate/state`; own logs:
  `../logs/sakura-proxy-logrotate`.
