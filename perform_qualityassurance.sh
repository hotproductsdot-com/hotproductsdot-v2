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
# STEP 2: Price validation (dry-run — reports mismatches, does not update CSV)
# ==============================================================================
step 2 "Price Validation (dry-run)"
echo -e "${YELLOW}  Note: Full price validation is slow (live Amazon scraping).${RESET}"
echo -e "${YELLOW}  Using --dry-run to report mismatches without updating CSV.${RESET}"
echo -e "${YELLOW}  Run 'node validate-prices-parallel.js' separately to apply fixes.${RESET}"
echo ""

cd "$SCRIPT_DIR"
PRICE_OUTPUT=$(node validate-prices-parallel.js --dry-run --workers=2 2>&1) || true

PRICE_WARNINGS=$(echo "$PRICE_OUTPUT" | grep -c "⚠" || true)
PRICE_CAPTCHA=$(echo "$PRICE_OUTPUT" | grep -c "CAPTCHA" || true)

echo "$PRICE_OUTPUT" | tail -20

if [ "$PRICE_CAPTCHA" -gt 0 ]; then
  warn "CAPTCHA hits during price check ($PRICE_CAPTCHA) — results may be incomplete"
fi

if [ "$PRICE_WARNINGS" -gt 0 ]; then
  warn "$PRICE_WARNINGS price mismatch(es) detected — run 'node validate-prices-parallel.js' to fix"
else
  pass "No price mismatches detected"
fi

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
