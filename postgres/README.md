# postgres

PostgreSQL container (`sakura-postgres`), image `postgres:${POSTGRES_VERSION}`.

- No configuration files: the container is configured entirely through the
  `POSTGRES_*` variables in `../.env` (`POSTGRES_DB`, `POSTGRES_USER`,
  `POSTGRES_PASSWORD`, `POSTGRES_PORT`).
- Data: bind mount `../data/postgres` on `/var/lib/postgresql/data`, with
  `PGDATA=/var/lib/postgresql/data/pgdata` so the volume root stays clean.
- Published only on the host loopback (`127.0.0.1:${POSTGRES_PORT}`).
- The integration test suite targets a separate throwaway database selected by
  `POSTGRES_TEST_DATABASE_URL`; never point it at this database.
