# sakura-proxy

Traefik container (`sakura-proxy`), image `traefik:${PROXY_TRAEFIK_VERSION}`.

- `config/traefik.yml`: static configuration (entrypoints, file provider,
  access log).
- `config/dynamic.yml`: routers and services that publish the bot health
  endpoint over TLS.
- Published port: `${PROXY_HTTPS_PORT}` → 443. The dashboard and the ping
  endpoint stay on the container loopback and are intentionally not published.
- No certificate is configured, so Traefik generates a self-signed one; replace
  it before exposing the endpoint outside the host.
- Access and error logs go to the named volume `sakura-proxy-logs`
  (`/var/log/traefik`) and are rotated by the `sakura-proxy-logrotate` sidecar.
