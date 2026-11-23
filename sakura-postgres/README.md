# sakura-postgres

PostgreSQL container (`sakura-postgres`), image `postgres:${POSTGRES_VERSION}`.

- No configuration files: the container is configured entirely through the
  `POSTGRES_*` variables in `../.env` (`POSTGRES_DB`, `POSTGRES_USER`,
  `POSTGRES_PASSWORD`, `POSTGRES_PORT`).
- Data: named volume `sakura-postgres-data` on `/var/lib/postgresql/data`, with
  `PGDATA=/var/lib/postgresql/data/pgdata` so the volume root stays clean.
- The volume survives image rebuilds and `docker compose down`; only
  `docker compose down -v` deletes it.
- Published only on the host loopback (`127.0.0.1:${POSTGRES_PORT}`).
- The integration test suite targets a separate throwaway database selected by
  `POSTGRES_TEST_DATABASE_URL`; never point it at this database.
