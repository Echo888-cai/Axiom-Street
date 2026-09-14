#!/usr/bin/env bash
# P6D backup/restore drill on the isolated axiom-e2e Postgres.
#
# 1. pg_dump the live isolated DB;
# 2. restore it into a FRESH scratch database;
# 3. verify alembic revision + row counts match, so a clean environment can be
#    rebuilt from the backup (recovery time and data-loss window are reported).
#
# Usage: scripts/p6-backup-restore.sh
set -euo pipefail

export DOCKER_HOST="${DOCKER_HOST:-unix://$HOME/.colima/default/docker.sock}"
ENV_FILE="${ENV_FILE:-$(pwd)/.env.example}"
PG_CONTAINER="${PG_CONTAINER:-axiom-e2e-postgres-1}"
SRC_DB="${SRC_DB:-street}"
SCRATCH_DB="${SCRATCH_DB:-street_restore_drill}"
BACKUP="${BACKUP:-/tmp/axiom-p6-backup.sql}"

# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a
PGUSER="${POSTGRES_USER:?set POSTGRES_USER}"

echo "==> [1/4] dump $SRC_DB to $BACKUP"
START=$(date +%s)
docker exec "$PG_CONTAINER" pg_dump -U "$PGUSER" -d "$SRC_DB" --clean --if-exists > "$BACKUP"
SIZE=$(wc -c < "$BACKUP" | tr -d ' ')
echo "backup bytes: $SIZE"

echo "==> [2/4] restore into fresh scratch database $SCRATCH_DB"
docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d postgres -c "DROP DATABASE IF EXISTS $SCRATCH_DB" >/dev/null
docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d postgres -c "CREATE DATABASE $SCRATCH_DB" >/dev/null
docker exec -i "$PG_CONTAINER" psql -U "$PGUSER" -d "$SCRATCH_DB" < "$BACKUP" >/dev/null
END=$(date +%s)

echo "==> [3/4] verify revision and key row counts"
REV_SRC=$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$SRC_DB" -tAc "select version_num from alembic_version")
REV_DST=$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$SCRATCH_DB" -tAc "select version_num from alembic_version")
STRAT_SRC=$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$SRC_DB" -tAc "select count(*) from strategies")
STRAT_DST=$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$SCRATCH_DB" -tAc "select count(*) from strategies")
WS_DST=$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$SCRATCH_DB" -tAc "select count(*) from workspaces")
echo "revision: $REV_SRC -> $REV_DST | strategies: $STRAT_SRC -> $STRAT_DST | workspaces: $WS_DST"
[ "$REV_SRC" = "$REV_DST" ] || { echo "REVISION MISMATCH"; exit 1; }
[ "$STRAT_SRC" = "$STRAT_DST" ] || { echo "ROW COUNT MISMATCH"; exit 1; }

echo "==> [4/4] cleanup scratch database"
docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d postgres -c "DROP DATABASE $SCRATCH_DB" >/dev/null

echo "==> DRILL DONE: restore time $((END-START))s, backup $SIZE bytes, revision $REV_DST, strategies $STRAT_DST"