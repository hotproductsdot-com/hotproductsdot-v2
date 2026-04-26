#!/usr/bin/env bash
# Daily routine: 3 IG posts -> build -> rsync to Hostinger.
# Resilient: individual post failures don't block the deploy.
set -uo pipefail

REPO="/mnt/e/GITHUB/hotproductsdot-v2"
cd "$REPO"

mkdir -p .omc/logs
LOG=".omc/logs/daily-$(date -u +%Y%m%d-%H%M).log"

# shellcheck disable=SC1091
source venv/bin/activate

{
  echo "=== START $(date -u +%FT%TZ) ==="
  posts_ok=0
  for i in 1 2 3; do
    echo
    echo "=== POST $i/3 $(date -u +%H:%M:%S) ==="
    if python post_daily.py --platform instagram; then
      posts_ok=$((posts_ok + 1))
    else
      echo "POST $i FAILED (continuing)"
    fi
  done
  echo
  echo "=== POSTS DONE: $posts_ok/3 successful ==="

  if [ "$posts_ok" -gt 0 ]; then
    echo "=== BUILD + RSYNC $(date -u +%H:%M:%S) ==="
    cd site && npm run deploy:rsync
  else
    echo "=== SKIP DEPLOY: no posts succeeded ==="
    exit 1
  fi

  echo "=== END $(date -u +%FT%TZ) ==="
} >>"$LOG" 2>&1
