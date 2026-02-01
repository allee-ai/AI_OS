#!/bin/bash
# Reset Demo Database
# Clears the demo database and WAL files, re-seeds with sample data

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DB_DIR="$REPO_ROOT/data/db"

echo ""
echo "🎮 Resetting Demo Database..."
echo ""

# Remove demo database and WAL files
rm -f "$DB_DIR/state_demo.db"
rm -f "$DB_DIR/state_demo.db-shm"
rm -f "$DB_DIR/state_demo.db-wal"
rm -f "$DB_DIR/demo.db"  # old naming

echo "✅ Cleared demo database files"

# Check if we need to initialize schema
# The schema should be created automatically by the app, but we can trigger it
if [ -f "$SCRIPT_DIR/seed_demo.sql" ]; then
    echo "🌱 Seeding demo data..."
    
    # First, we need to create the tables. The app does this on startup.
    # For standalone reset, we need to run Python to initialize schema
    cd "$REPO_ROOT"
    python3 -c "
from data.db import set_demo_mode, DEMO_DB
from agent.threads.identity.db import init_db as init_identity
from agent.threads.log.db import init_db as init_log
from agent.threads.linking_core.db import init_db as init_linking

# Switch to demo mode
set_demo_mode(True)

# Initialize all schemas
init_identity()
init_log()
init_linking()

print('✅ Schema initialized')
"
    
    # Now seed the data
    sqlite3 "$DB_DIR/state_demo.db" < "$SCRIPT_DIR/seed_demo.sql"
    echo "✅ Demo data seeded"
else
    echo "⚠️  No seed_demo.sql found, skipping seed step"
fi

echo ""
echo "🎮 Demo database reset complete!"
echo "   Path: $DB_DIR/state_demo.db"
echo ""
