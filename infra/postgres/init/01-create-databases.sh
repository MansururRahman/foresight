#!/bin/bash
# Runs once, on first initialisation of the postgres data volume.
# Creates two isolated application roles and databases (plus test twins).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  CREATE ROLE foresight_auth LOGIN PASSWORD '${AUTH_DB_PASSWORD}';
  CREATE ROLE foresight_api  LOGIN PASSWORD '${API_DB_PASSWORD}';
  CREATE DATABASE foresight_auth      OWNER foresight_auth;
  CREATE DATABASE foresight_api       OWNER foresight_api;
  CREATE DATABASE foresight_auth_test OWNER foresight_auth;
  CREATE DATABASE foresight_api_test  OWNER foresight_api;
  REVOKE CONNECT ON DATABASE foresight_auth      FROM PUBLIC;
  REVOKE CONNECT ON DATABASE foresight_api       FROM PUBLIC;
  REVOKE CONNECT ON DATABASE foresight_auth_test FROM PUBLIC;
  REVOKE CONNECT ON DATABASE foresight_api_test  FROM PUBLIC;
EOSQL

for db in foresight_auth foresight_auth_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" \
    -c "CREATE EXTENSION IF NOT EXISTS citext;"
done

for db in foresight_api foresight_api_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" \
    -c "CREATE EXTENSION IF NOT EXISTS citext; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
done
