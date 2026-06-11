#!/usr/bin/env bash
# Start all Agentic OS services including external dashboards
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

bash "$REPO/agentic-os/scripts/start-external-services.sh"

echo
echo "Starting Mission Control on :9120..."
pkill -f "agentic-os/mission-control/server.py" 2>/dev/null || true
fuser -k 9120/tcp 2>/dev/null || true
sleep 1
cd "$REPO"
nohup python3 agentic-os/mission-control/server.py > ~/.hermes/logs/mission-control.log 2>&1 &
sleep 1

echo
echo "All services:"
echo "  Mission Control  → http://127.0.0.1:9120"
echo "  Hermes Dashboard → http://127.0.0.1:9119"
echo "  Hermes Desktop   → native Electron app (click sidebar or run: hermes desktop)"
echo "  Pipeline UI      → http://127.0.0.1:7878"
echo "  Deal Poster      → http://127.0.0.1:5050"
