#!/usr/bin/env bash
# Install Agentic OS into Hermes (~/.hermes) — Jack Roberts architecture
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
AGENTIC="$REPO/agentic-os"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

echo "╔══════════════════════════════════════════╗"
echo "║  Agentic OS Install — Hermes + Pantheon  ║"
echo "╚══════════════════════════════════════════╝"
echo "Repo:  $REPO"
echo "Hermes: $HERMES_HOME"
echo

# 1. Verify Hermes
if ! command -v hermes &>/dev/null; then
  echo "Hermes not found. Install first:"
  echo "  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
  exit 1
fi
echo "✓ Hermes $(hermes --version 2>/dev/null | head -1)"

# 2. Sync Pantheon + skills + SOUL
echo
echo "→ Syncing Pantheon personas and skills..."
python3 "$AGENTIC/scripts/sync-pantheon.py"

# 3. Portfolio harness (primary repo)
echo
echo "→ Refreshing portfolio harness on primary repo..."
python3 "$AGENTIC/harness/install.py" --project "$REPO" 2>&1 || true

# 4. Bridge context
echo
echo "→ Collecting Claude OS bridge context..."
python3 "$AGENTIC/bridge/collect_context.py"

# 5. Cron jobs (idempotent — skip if already exist)
echo
echo "→ Setting up cron jobs..."
setup_cron() {
  local name="$1"
  shift
  if hermes cron list 2>/dev/null | grep -q "$name"; then
    echo "  cron '$name' already exists — skip"
  else
    echo "  creating cron: $name"
    HERMES_ACCEPT_HOOKS=1 hermes cron create "$@" --name "$name" 2>&1 || true
  fi
}

# Bridge refresh script must live in ~/.hermes/scripts/
mkdir -p "$HERMES_HOME/scripts"
cp "$AGENTIC/bridge/collect_context.py" "$HERMES_HOME/scripts/collect_bridge_context.py"

setup_cron "morning-brief" \
  "0 8 * * *" \
  "You are Mercury. Read agentic-os/bridge/context/latest.json and growth-engine/data/*.json. Deliver a morning brief: 1) growth-engine status 2) top 2-3 improvement suggestions from bridge 3) any stale tasks. Keep it under 300 words." \
  --workdir "$REPO" \
  --skill pantheon \
  --skill claude-os-bridge \
  --skill hotproducts-growth \
  --deliver local

setup_cron "bridge-refresh" \
  "0 */4 * * *" \
  --script collect_bridge_context.py \
  --no-agent \
  --deliver local

setup_cron "github-backup" \
  "0 23 * * *" \
  "Backup Hermes config: copy ~/.hermes/config.yaml, SOUL.md, and agentic-os/config/personalities.yaml to the agentic-os backup folder in the repo if changed. Report what was updated." \
  --workdir "$REPO" \
  --skill pantheon \
  --deliver local

# 6. MCP bridge hints
echo
echo "→ MCP bridge config written to agentic-os/config/"
echo "  Apply Cursor MCP: copy config/cursor-mcp.json → .cursor/mcp.json"

# 7. Obsidian (already in config if set)
if grep -q OBSIDIAN_VAULT_PATH "$HERMES_HOME/config.yaml" 2>/dev/null; then
  echo "✓ Obsidian vault already configured in Hermes"
else
  echo "  Tip: add OBSIDIAN_VAULT_PATH to ~/.hermes/config.yaml"
fi

echo
echo "══════════════════════════════════════════"
echo "Done! Next steps:"
echo "  1. hermes gateway setup && hermes gateway start   # Telegram"
echo "  2. hermes dashboard --tui --port 9119             # Hermes UI"
echo "  3. python3 agentic-os/mission-control/server.py   # Mission Control :9120"
echo "  4. hermes mcp serve                               # Cursor bridge"
echo "══════════════════════════════════════════"
