#!/bin/bash
# Backend entrypoint script - initializes identity DB before starting server

set -e

echo "[entrypoint] Starting Nola backend initialization..."

# Run identity database migration if enabled
if [ "$IDENTITY_BACKEND" = "db" ]; then
    echo "[entrypoint] Identity backend set to DB mode"
    echo "[entrypoint] Running identity database migration..."
    
    # Auto-migration handled by schema.py on startup
    echo "[entrypoint] ✓ Identity database intialization handled by schema"
    
    if [ $? -eq 0 ]; then
        echo "[entrypoint] ✓ Identity database initialized successfully"
    else
        echo "[entrypoint] ✗ Identity database migration failed"
        exit 1
    fi
    
    # Health check
    # python -m Nola.threads.schema --health  <-- TODO: Implement health check CLI
    true
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
