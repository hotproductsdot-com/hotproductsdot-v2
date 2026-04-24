#!/usr/bin/env bash
# ==============================================================================
# perform_qualityassurance.sh
# QA pipeline: Lint → Price check → Image check → Production build
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

PASS=0
FAIL=0
WARNINGS=0

step() {
  echo ""
  echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo -e "${CYAN}${BOLD}  STEP $1: $2${RESET}"
  echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
}

pass() {
  echo -e "${GREEN}  ✔ $1${RESET}"
  PASS=$((PASS + 1))
}

fail() {
  echo -e "${RED}  ✘ $1${RESET}"
  FAIL=$((FAIL + 1))
}

warn() {
  echo -e "${YELLOW}  ⚠ $1${RESET}"
  WARNINGS=$((WARNINGS + 1))
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="$SCRIPT_DIR/site"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║        QA PIPELINE — hotproductsdot-v2       ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${RESET}"
echo -e "  Started: $(date '+%Y-%m-%d %H:%M:%S')"

# ==============================================================================
# STEP 1: ESLint
# ==============================================================================
step 1 "ESLint"

cd "$SITE_DIR"
if npm run lint --silent 2>&1; then
  pass "No lint errors"
else
  LINT_EXIT=$?
  fail "Lint failed (exit $LINT_EXIT) — fix errors before building"
  echo -e "${RED}  Aborting pipeline.${RESET}"
  exit 1
fi

# ==============================================================================
# STEP 2: Price validation (manual — Oxylabs API costs per call, not run in QA)
# ==============================================================================
step 2 "Price Validation (skipped — run manually)"
echo -e "${YELLOW}  Price/rating/review validation is handled by ./oxylabs-amazon-product.sh${RESET}"
echo -e "${YELLOW}  (Oxylabs Amazon Product API — structured JSON, CAPTCHA-free).${RESET}"
echo -e "${YELLOW}  Not run from QA because each API call has a cost.${RESET}"
echo -e "${YELLOW}  Run manually before launches or on cron:${RESET}"
echo -e "${YELLOW}    ./oxylabs-amazon-product.sh --limit 20     # sample check${RESET}"
echo -e "${YELLOW}    ./oxylabs-amazon-product.sh                # full catalog refresh${RESET}"
pass "Price validation step is manual (see ./oxylabs-amazon-product.sh)"

# ==============================================================================
# STEP 3: Image check
# ==============================================================================
step 3 "Image Check"

cd "$SCRIPT_DIR"
IMAGE_OUTPUT=$(node check-images.js 2>&1)
echo "$IMAGE_OUTPUT"

MISSING_COUNT=$(echo "$IMAGE_OUTPUT" | grep "^Missing images:" | grep -o '[0-9]*' || echo "0")

if [ "$MISSING_COUNT" -eq 0 ]; then
  pass "All product images present"
elif [ "$MISSING_COUNT" -lt 10 ]; then
  warn "$MISSING_COUNT image(s) missing — run 'node download-missing.js' to fix"
else
  fail "$MISSING_COUNT images missing — run 'node download-missing.js' before deploying"
  echo -e "${RED}  Aborting pipeline.${RESET}"
  exit 1
fi

# ==============================================================================
# STEP 4: Production build
# ==============================================================================
step 4 "Production Build"

cd "$SITE_DIR"
if npm run build 2>&1; then
  pass "Production build succeeded"
else
  BUILD_EXIT=$?
  fail "Production build failed (exit $BUILD_EXIT)"
  exit 1
fi

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║                  QA SUMMARY                  ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${RESET}"
echo -e "  Completed: $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "  ${GREEN}Passed:   $PASS${RESET}"
echo -e "  ${YELLOW}Warnings: $WARNINGS${RESET}"
echo -e "  ${RED}Failed:   $FAIL${RESET}"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo -e "${RED}${BOLD}  ✘ QA FAILED — do not deploy${RESET}"
  exit 1
elif [ "$WARNINGS" -gt 0 ]; then
  echo -e "${YELLOW}${BOLD}  ⚠ QA PASSED WITH WARNINGS — review before deploying${RESET}"
  exit 0
else
  echo -e "${GREEN}${BOLD}  ✔ QA PASSED — ready to deploy${RESET}"
  exit 0
fi
