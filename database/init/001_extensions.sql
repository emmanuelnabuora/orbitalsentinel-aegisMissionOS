-- Run once at cluster init (docker-entrypoint-initdb.d).
-- Application schema is owned by Alembic migrations, never by init scripts.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy search over asset/alert names
