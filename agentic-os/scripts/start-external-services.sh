#!/usr/bin/env bash
# Start Mission Control external services (web UIs + Hermes Desktop)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="${HOME}/.hermes/logs"
mkdir -p "$LOG_DIR"

export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

start_if_down() {
  local port="$1"
  if curl -sf -o /dev/null --connect-timeout 1 "http://127.0.0.1:${port}/" 2>/dev/null; then
    echo "  :${port} already up"
    return 0
  fi
  return 1
}

echo "=== External services ==="

# 1. Hermes Dashboard :9119
if ! start_if_down 9119; then
  echo "Starting Hermes Dashboard on :9119..."
  pkill -f "hermes dashboard" 2>/dev/null || true
  fuser -k 9119/tcp 2>/dev/null || true
  sleep 1
  # --skip-build avoids npm hang in headless; build dist if missing
  HERMES_WEB="$HOME/.hermes/hermes-agent/web"
  if [[ -d "$HERMES_WEB" && ! -d "$HERMES_WEB/dist" ]]; then
    echo "  Building Hermes dashboard UI (first run)..."
    (cd "$HERMES_WEB" && npm install --silent 2>/dev/null && npm run build 2>"$LOG_DIR/dashboard-build.log") || true
  fi
  nohup hermes dashboard --no-open --port 9119 --skip-build \
    > "$LOG_DIR/dashboard.log" 2>&1 &
  sleep 3
fi

# 2. Pipeline UI :7878
if ! start_if_down 7878; then
  echo "Starting Pipeline UI on :7878..."
  pkill -f "pipeline-ui/server.py" 2>/dev/null || true
  fuser -k 7878/tcp 2>/dev/null || true
  sleep 1
  nohup python3 "$REPO/pipeline-ui/server.py" > "$LOG_DIR/pipeline-ui.log" 2>&1 &
  sleep 2
fi

# 3. Deal Poster :5050
if ! start_if_down 5050; then
  echo "Starting Deal Poster on :5050..."
  pkill -f "growth-engine/web_ui.py" 2>/dev/null || true
  fuser -k 5050/tcp 2>/dev/null || true
  sleep 1
  if ! python3 -c "import flask" 2>/dev/null; then
    echo "  Installing flask for deal poster..."
    pip install -q flask
  fi
  nohup python3 "$REPO/growth-engine/web_ui.py" > "$LOG_DIR/deal-poster.log" 2>&1 &
  sleep 2
fi

# 4. Hermes Desktop (Electron native app)
desktop_running() {
  pgrep -f 'linux-unpacked/Hermes|apps/desktop/release' >/dev/null 2>&1
}
if desktop_running; then
  echo "  Hermes Desktop already running"
else
  echo "Starting Hermes Desktop..."
  DESKTOP_RELEASE="$HOME/.hermes/hermes-agent/apps/desktop/release/linux-unpacked/Hermes"
  DESKTOP_ARGS=(hermes desktop)
  if [[ -x "$DESKTOP_RELEASE" ]]; then
    DESKTOP_ARGS+=(--skip-build)
  fi
  if [[ -z "${DISPLAY:-}" && -e /mnt/wslg/runtime-dir/wayland-0 ]]; then
    export DISPLAY=:0
    export WAYLAND_DISPLAY=wayland-0
  fi
  nohup "${DESKTOP_ARGS[@]}" > "$LOG_DIR/desktop.log" 2>&1 &
  sleep 2
fi

echo
echo "Status:"
for port in 9119 7878 5050; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 "http://127.0.0.1:${port}/" 2>/dev/null || echo "000")
  case "$port" in
    9119) name="Hermes Dashboard" ;;
    7878) name="Pipeline UI     " ;;
    5050) name="Deal Poster     " ;;
  esac
  if [[ "$code" == "200" || "$code" == "302" || "$code" == "301" ]]; then
    echo "  OK  ${name}  http://127.0.0.1:${port}  (${code})"
  else
    echo "  FAIL ${name}  http://127.0.0.1:${port}  (${code})"
    case "$port" in
      9119) echo "       log: $LOG_DIR/dashboard.log" ;;
      7878) echo "       log: $LOG_DIR/pipeline-ui.log" ;;
      5050) echo "       log: $LOG_DIR/deal-poster.log" ;;
    esac
  fi
done
if desktop_running; then
  echo "  OK  Hermes Desktop   (native app)"
else
  echo "  FAIL Hermes Desktop   (native app)"
  echo "       log: $LOG_DIR/desktop.log"
fi
