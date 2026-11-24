# sakura-proxy

> **Historical material.** This container is no longer part of any active Compose
> file: the bot connects outbound to the Discord Gateway, so no inbound proxy is
> needed and the probes are read with `docker compose exec`. The folder is kept
> only for rollback and for the operator to decide when to remove it.

Traefik container (`sakura-proxy`), image
`traefik:${SAKURA_PROXY_TRAEFIK_VERSION}`.

- `config/traefik.yml`: static configuration (entrypoints, file provider,
  access log).
- `config/dynamic.yml`: router and service that publish only `Path(`/health`)`
  over TLS. `/ready` is deliberately not routed, so the readiness diagnostics
  stay reachable only inside the Docker network.
- Published port: `127.0.0.1:${SAKURA_PROXY_HTTPS_PORT}` → 443, loopback only.
  The dashboard and the ping endpoint stay on the container loopback and are
  intentionally not published.
- No certificate is configured, so Traefik generates a self-signed one; replace
  it before exposing the endpoint outside the host.
- Access and error logs go to the named volume `sakura-proxy-logs`
  (`/var/log/traefik`) and are rotated by the `sakura-proxy-logrotate` sidecar.
