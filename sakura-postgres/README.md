# sakura-postgres

PostgreSQL container (`sakura-postgres`), image
`postgres:${SAKURA_POSTGRES_VERSION}`.

- No configuration files: the container is configured entirely through the
  `SAKURA_POSTGRES_*` variables in `../.env` (`SAKURA_POSTGRES_DB`,
  `SAKURA_POSTGRES_USER`, `SAKURA_POSTGRES_PASSWORD`, `SAKURA_POSTGRES_PORT`).
  `docker-compose.yml` maps them to the `POSTGRES_DB`, `POSTGRES_USER` and
  `POSTGRES_PASSWORD` names the official image reads, so the prefix never
  reaches the container.
- Data: named volume `sakura-postgres-data` on `/var/lib/postgresql/data`, with
  `PGDATA=/var/lib/postgresql/data/pgdata` so the volume root stays clean.
- The volume survives image rebuilds and `docker compose down`; only
  `docker compose down -v` deletes it.
- Published only on the host loopback (`127.0.0.1:${SAKURA_POSTGRES_PORT}`).
- The integration test suite targets a separate throwaway database selected by
  `SAKURA_POSTGRES_TEST_DATABASE_URL`; never point it at this database. The
  dedicated cluster is defined in `../docker-compose.test.yml`
  (`sakura-postgres-test`, tmpfs storage, own network and credentials).
