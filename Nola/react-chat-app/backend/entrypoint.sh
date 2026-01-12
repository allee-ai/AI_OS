#!/bin/bash
# Backend entrypoint script - initializes identity DB before starting server

set -e

echo "[entrypoint] Starting Nola backend initialization..."

# Run identity database migration if enabled
if [ "$IDENTITY_BACKEND" = "db" ]; then
    echo "[entrypoint] Identity backend set to DB mode"
    echo "[entrypoint] Running identity database migration..."
    
    # Run the idv2 migration
    cd /app
    python -m Nola.idv2.idv2 --migrate
    
    if [ $? -eq 0 ]; then
        echo "[entrypoint] ✓ Identity database initialized successfully"
    else
        echo "[entrypoint] ✗ Identity database migration failed"
        exit 1
    fi
    
    # Health check
    python -m Nola.idv2.idv2 --health
    if [ $? -eq 0 ]; then
        echo "[entrypoint] ✓ Identity database health check passed"
    else
        echo "[entrypoint] ✗ Identity database health check failed"
        exit 1
    fi
else
    echo "[entrypoint] Identity backend set to JSON mode (default)"
fi

echo "[entrypoint] Starting uvicorn server..."

# Execute the main command (passed as arguments to this script)
exec "$@"
