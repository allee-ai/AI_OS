#!/usr/bin/env bash
# shadow/run_shadow_test.sh
#
# Copy the live DB, boot a shadow container, apply a pending
# improvement, run verification, report pass/fail.  Does NOT touch the
# live container.
#
# Usage: ./shadow/run_shadow_test.sh [improvement_id]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SHADOW_DB="${ROOT}/data/db/state.shadow.db"
LIVE_DB="${ROOT}/data/db/state.db"

echo "[shadow] Preparing shadow DB copy"
cp -f "${LIVE_DB}" "${SHADOW_DB}"

echo "[shadow] Ensuring shadow container is up"
cd "${ROOT}/shadow"
docker compose up -d aios_shadow

echo "[shadow] Waiting for shadow to answer on :8001"
for i in $(seq 1 30); do
    if curl -fsS http://localhost:8001/api/subconscious/heartbeat \
            >/dev/null 2>&1; then
        echo "[shadow] up"
        break
    fi
    sleep 1
done

echo "[shadow] Running write-bus verification"
docker exec aios_shadow python /app/tmp/verify_write_bus.py && \
    echo "[shadow] PASS" || \
    { echo "[shadow] FAIL"; exit 1; }

echo "[shadow] Shadow test complete"
