#!/usr/bin/env bash
# start-backend.sh
# Mac/Linux equivalent of start-backend.ps1.  Kills anything listening on
# the backend port, then runs uvicorn fresh with --reload.
#
# Usage:
#   ./start-backend.sh         # uses port 8001
#   PORT=8000 ./start-backend.sh

set -e

PORT="${PORT:-8001}"

echo "[start-backend] Looking for processes on port ${PORT} ..."
if command -v lsof >/dev/null 2>&1; then
    PIDS=$(lsof -ti "tcp:${PORT}" 2>/dev/null || true)
    if [ -n "${PIDS}" ]; then
        echo "[start-backend] Killing PIDs: ${PIDS}"
        # shellcheck disable=SC2086
        kill -9 ${PIDS} 2>/dev/null || true
        sleep 1
    fi
else
    echo "[start-backend] lsof not available; skipping zombie cleanup."
fi

cd "$(dirname "$0")/backend"
echo "[start-backend] Starting uvicorn on http://127.0.0.1:${PORT} ..."
exec uvicorn main:app --host 127.0.0.1 --port "${PORT}" --reload
