#!/bin/bash
# Mirror the droplet's Postgres database INTO the local database.
# Run this when the droplet is reachable. It is destructive on the LOCAL db only.
#
# Usage:
#   bash pull_from_droplet.sh             # backup local, then mirror
#   bash pull_from_droplet.sh --dry-run   # just download the dump, don't apply
set -e
cd "$(dirname "$0")"

SERVER="root@159.223.195.100"
REMOTE_DB="jake_app"
REMOTE_USER="jake_app"
REMOTE_PASS="jk_pg_2026"
LOCAL_DB="jake_app"

STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="data/backups"
mkdir -p "$BACKUP_DIR"
DUMP="$BACKUP_DIR/droplet_${STAMP}.sql"
LOCAL_BAK="$BACKUP_DIR/local_before_${STAMP}.sql"

echo "=== Dumping droplet $REMOTE_DB → $DUMP ==="
ssh -o ConnectTimeout=15 "$SERVER" \
  "PGPASSWORD='$REMOTE_PASS' pg_dump -h localhost -U $REMOTE_USER --clean --if-exists --no-owner --no-privileges $REMOTE_DB" \
  > "$DUMP"
echo "  $(wc -l < "$DUMP") lines"

if [ "$1" = "--dry-run" ]; then
  echo "Dry run — dump saved at $DUMP. Not applied."
  exit 0
fi

echo "=== Backing up local $LOCAL_DB → $LOCAL_BAK ==="
pg_dump --clean --if-exists --no-owner --no-privileges "$LOCAL_DB" > "$LOCAL_BAK"

echo "=== Restoring droplet dump into local $LOCAL_DB ==="
psql -v ON_ERROR_STOP=1 -q "$LOCAL_DB" < "$DUMP"

echo ""
echo "Done. Local mirrors droplet."
echo "  droplet dump: $DUMP"
echo "  local backup: $LOCAL_BAK   (to roll back: psql $LOCAL_DB < $LOCAL_BAK)"
