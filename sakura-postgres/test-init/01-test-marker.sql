-- Marker table created only by the throwaway test stack.
--
-- tests/support/database_guard.py refuses to drop a schema unless this row is
-- present, so a URL that points at the application cluster (or at any other
-- PostgreSQL instance) is rejected before the first DDL statement.
CREATE TABLE IF NOT EXISTS sakura_test_marker (
    marker text PRIMARY KEY
);

INSERT INTO sakura_test_marker (marker)
VALUES ('sakura-destructive-test-database')
ON CONFLICT (marker) DO NOTHING;
