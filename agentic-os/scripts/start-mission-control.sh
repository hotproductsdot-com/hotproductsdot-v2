#!/usr/bin/env bash
# Start Mission Control dashboard (kills stale process on port 9120 first)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${MISSION_CONTROL_PORT:-9120}"

pkill -f "agentic-os/mission-control/server.py" 2>/dev/null || true
fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 1

cd "$REPO"
echo "Starting Mission Control on port ${PORT}..."
exec python3 agentic-os/mission-control/server.py
