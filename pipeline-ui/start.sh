#!/usr/bin/env bash
# HotProducts Pipeline UI launcher.
# Activates the project venv if present, then starts the local web server.

set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
cd "$REPO"

if [ -d "venv" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

PY=${PYTHON:-python3}
exec "$PY" "$HERE/server.py" "$@"
