#!/usr/bin/env bash
# run_daily_deals.sh — cron entrypoint for the daily Limited Time Sale refresh.
#
# Runs fetch_daily_deals.py against origin/main in a detached git worktree so
# the developer checkout (often on a feature branch, possibly dirty) is never
# touched, then commits + pushes the updated catalog/images to main. The
# 14:00 UTC daily_post.yml workflow then posts the top 5 deals to Instagram
# and rebuilds/deploys the site with the new Limited Time Sale section.
#
# Cron (local time is America/Chicago on this machine):
#   0 8 * * * /mnt/e/GITHUB/hotproductsdot-v2/run_daily_deals.sh >> /mnt/e/GITHUB/hotproductsdot-v2/logs/daily_deals.log 2>&1

set -euo pipefail

REPO="/mnt/e/GITHUB/hotproductsdot-v2"
WORKTREE="/mnt/e/GITHUB/.hotproducts-deals-worktree"
PYTHON="$REPO/venv/bin/python3"
[[ -x "$PYTHON" ]] || PYTHON="python3"

echo "════════════════════════════════════════════════════"
echo "daily-deals run: $(date '+%Y-%m-%d %H:%M:%S %Z')"

cd "$REPO"
git fetch --quiet origin main

# Detached worktree: holds no branch ref, so the dev checkout can still
# `git checkout main` without conflicts.
if [[ ! -d "$WORKTREE" ]]; then
  git worktree add --detach "$WORKTREE" origin/main
fi
git -C "$WORKTREE" checkout --quiet --detach origin/main
git -C "$WORKTREE" reset --hard --quiet origin/main

# .env is gitignored — the worktree needs the Oxylabs credentials.
if [[ -f "$REPO/.env" && ! -f "$WORKTREE/.env" ]]; then
  cp "$REPO/.env" "$WORKTREE/.env"
fi

# fetch_daily_deals.py resolves all paths relative to its own location, so
# running the worktree copy operates entirely on worktree files. Exit code 2
# (zero qualifying deals) leaves the catalog untouched — nothing to commit,
# and yesterday's deals stay live rather than shipping an empty section.
set +e
"$PYTHON" "$WORKTREE/fetch_daily_deals.py"
rc=$?
set -e
if [[ $rc -eq 2 ]]; then
  echo "No qualifying deals today (rc=2) — keeping yesterday's batch, no push."
  exit 0
elif [[ $rc -ne 0 ]]; then
  echo "fetch_daily_deals.py failed (rc=$rc) — aborting."
  exit "$rc"
fi

cd "$WORKTREE"
# products/discovery/ is gitignored (regenerated per run) — adding it makes
# git add exit 1, which kills the script under set -e before commit/push.
git add products/top-1000.csv site/public/products
if git diff --staged --quiet; then
  echo "No catalog changes — nothing to push."
  exit 0
fi

git -c user.email="cron@hotproductsdot.com" -c user.name="Daily Deals Cron" \
  commit --quiet -m "feat: limited-time sale batch $(date +%F) [skip ci]"

# Push with one rebase retry in case something landed on main since fetch.
# (fetch+rebase, not pull --rebase — the worktree HEAD is detached.)
if ! git push --quiet origin HEAD:main; then
  git fetch --quiet origin main
  git rebase --quiet origin/main
  git push --quiet origin HEAD:main
fi
echo "Pushed $(git rev-parse --short HEAD) to main."
