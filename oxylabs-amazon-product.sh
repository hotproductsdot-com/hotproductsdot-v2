#!/usr/bin/env bash
# Oxylabs Amazon Product batch checker.
# Backs up products/top-1000.csv to a dated file, reads ASINs (5 at a time),
# queries Oxylabs for live data, writes differences to products4review.csv,
# and merges Price Range, Rating, and Review Count changes back into top-1000.csv.
#
# Usage:
#   chmod +x oxylabs-amazon-product.sh
#   ./oxylabs-amazon-product.sh [--limit N] [--geo GEO] [--offset N]
#
# Options:
#   --limit  N    Only process N products (default: all)
#   --geo    GEO  Geo location zip code (default: 90210)
#   --offset N    Skip the first N products (default: 0)
#
# Examples:
#   ./oxylabs-amazon-product.sh                        # process all
#   ./oxylabs-amazon-product.sh --limit 50             # first 50
#   ./oxylabs-amazon-product.sh --limit 10 --offset 20 # rows 21-30

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

if [[ -z "${OXYLABS_USERNAME:-}" || -z "${OXYLABS_PASSWORD:-}" ]]; then
  echo "Set OXYLABS_USERNAME and OXYLABS_PASSWORD in .env (see .env.example)." >&2
  exit 1
fi

# ── Defaults ──────────────────────────────────────────────────────────────────
GEO="90210"
LIMIT=0          # 0 = no limit
OFFSET=0
BATCH_SIZE=5
CSV_FILE="$REPO_ROOT/products/top-1000.csv"
OUTPUT_FILE="$REPO_ROOT/products/products4review.csv"

# ── Argument parsing ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --geo)    GEO="$2";    shift 2 ;;
    --limit)  LIMIT="$2";  shift 2 ;;
    --offset) OFFSET="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ── Dependency check ───────────────────────────────────────────────────────────
for cmd in curl python3; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Required command not found: $cmd" >&2
    exit 1
  fi
done

if [[ ! -f "$CSV_FILE" ]]; then
  echo "CSV not found: $CSV_FILE" >&2
  exit 1
fi

# ── Dated backup of top-1000.csv (before any live merge) ─────────────────────
BACKUP_STAMP=$(date +%Y-%m-%d)
BACKUP_FILE="${CSV_FILE%.csv}.backup.${BACKUP_STAMP}.csv"
if [[ -f "$BACKUP_FILE" ]]; then
  BACKUP_FILE="${CSV_FILE%.csv}.backup.${BACKUP_STAMP}_$(date +%H%M%S).csv"
fi
cp "$CSV_FILE" "$BACKUP_FILE"
echo "Backup created: $BACKUP_FILE"

# ── Write output header if file doesn't exist ──────────────────────────────────
if [[ ! -f "$OUTPUT_FILE" ]]; then
  echo "ASIN,Product Name,Field,CSV Value,Live Value" > "$OUTPUT_FILE"
  echo "Created output file: $OUTPUT_FILE"
fi

# ── Extract rows from CSV using Python (handles quoting/encoding properly) ─────
TMP_ROWS=$(mktemp /tmp/oxylabs_rows_XXXXXX.tsv)
TMP_UPDATES=$(mktemp /tmp/oxylabs_updates_XXXXXX.tsv)
trap 'rm -f "$TMP_ROWS" "$TMP_UPDATES"' EXIT

# Sentinel: field unchanged (tabs/newlines must not appear in live values)
readonly _NOCHANGE='__NOCHANGE__'

python3 - <<PYEOF > "$TMP_ROWS"
import csv

csv_file = r"$CSV_FILE"
limit     = int("$LIMIT")
offset    = int("$OFFSET")

with open(csv_file, encoding='utf-8-sig', errors='replace', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

rows = rows[offset:]
if limit > 0:
    rows = rows[:limit]

for r in rows:
    asin = (r.get('ASIN') or '').strip()
    if not asin:
        continue
    name    = (r.get('Product Name')    or '').replace('\t', ' ')
    price   = (r.get('Price Range')     or '').strip()
    rating  = (r.get('Rating')          or '').strip()
    reviews = (r.get('Review Count')    or '').strip()
    bsr     = (r.get('BSR')             or '').strip()
    print('\t'.join([asin, name, price, rating, reviews, bsr]))
PYEOF

# ── Count rows to process ──────────────────────────────────────────────────────
TOTAL=$(wc -l < "$TMP_ROWS" | tr -d ' ')
echo "Products to check : $TOTAL (batch size: $BATCH_SIZE)"
echo "Output file       : $OUTPUT_FILE"
echo "─────────────────────────────────────────────────────"

if [[ "$TOTAL" -eq 0 ]]; then
  echo "No products with ASINs found."
  exit 0
fi

# ── Helper: escape a value for CSV output ─────────────────────────────────────
escape_csv() {
  local val="${1//\"/\"\"}"
  echo "\"$val\""
}

# ── Helper: query Oxylabs for one ASIN, return raw JSON ───────────────────────
query_asin() {
  local asin="$1"
  curl -s 'https://realtime.oxylabs.io/v1/queries' \
    --user "${OXYLABS_USERNAME}:${OXYLABS_PASSWORD}" \
    -H "Content-Type: application/json" \
    -d "{
          \"source\": \"amazon_product\",
          \"query\": \"${asin}\",
          \"geo_location\": \"${GEO}\",
          \"parse\": true
        }"
}


# ── Helper: normalize price to a plain number for comparison ──────────────────
normalize_price() {
  echo "$1" | tr -d '$,' | sed 's/[[:space:]]//g' | cut -d'-' -f1
}

# ── Main loop ─────────────────────────────────────────────────────────────────
DIFF_COUNT=0
CHECKED=0
BATCH_NUM=0
BATCH_LINES=()

process_batch() {
  BATCH_NUM=$(( BATCH_NUM + 1 ))
  echo ""
  echo "── Batch $BATCH_NUM (${#BATCH_LINES[@]} products) ──────────────────────────────"

  for entry in "${BATCH_LINES[@]}"; do
    IFS=$'\t' read -r ASIN NAME CSV_PRICE CSV_RATING CSV_REVIEWS CSV_BSR <<< "$entry"
    CHECKED=$(( CHECKED + 1 ))
    echo "  [$CHECKED/$TOTAL] $ASIN  |  $NAME"

    # Query and save response to a temp file (avoids stdin conflicts with heredoc)
    TMP_RESP=$(mktemp /tmp/oxylabs_resp_XXXXXX.json)
    query_asin "$ASIN" > "$TMP_RESP"

    # Parse via Python (no jq needed)
    PARSED=$(python3 -c "
import json, sys
try:
    with open(r'$TMP_RESP') as f:
        data = json.load(f)
    content = data['results'][0]['content']
    status  = str(data['results'][0].get('status_code', '200'))
    if status != '200':
        print(f'ERROR:{status}')
        sys.exit(0)
    price   = str(content.get('price')         or '').strip()
    rating  = str(content.get('rating')        or '').strip()
    reviews = str(content.get('reviews_count') or '').strip()
    bsr_list = content.get('bestsellers_rank') or []
    bsr = str(bsr_list[0].get('rank') if bsr_list else '').strip()
    print('\t'.join([price, rating, reviews, bsr]))
except Exception as e:
    print(f'PARSE_ERROR:{e}')
")
    rm -f "$TMP_RESP"

    # Handle API / parse errors
    if [[ "$PARSED" == ERROR:* || "$PARSED" == PARSE_ERROR:* ]]; then
      echo "    ⚠  Skipping ($PARSED)"
      continue
    fi

    IFS=$'\t' read -r LIVE_PRICE LIVE_RATING LIVE_REVIEWS LIVE_BSR <<< "$PARSED"

    FOUND_DIFF=false

    check_field() {
      local field="$1" csv_val="$2" live_val="$3"
      if [[ -n "$live_val" && "$csv_val" != "$live_val" ]]; then
        echo "    ↳ DIFF  $field: CSV='$csv_val'  →  LIVE='$live_val'"
        printf '%s,%s,%s,%s,%s\n' \
          "$(escape_csv "$ASIN")" \
          "$(escape_csv "$NAME")" \
          "$(escape_csv "$field")" \
          "$(escape_csv "$csv_val")" \
          "$(escape_csv "$live_val")" >> "$OUTPUT_FILE"
        DIFF_COUNT=$(( DIFF_COUNT + 1 ))
        FOUND_DIFF=true
      fi
    }

    CSV_PRICE_N=$(normalize_price "$CSV_PRICE")
    LIVE_PRICE_N=$(normalize_price "$LIVE_PRICE")

    check_field "Price"        "$CSV_PRICE_N"  "$LIVE_PRICE_N"
    check_field "Rating"       "$CSV_RATING"   "$LIVE_RATING"
    check_field "Review Count" "$CSV_REVIEWS"  "$LIVE_REVIEWS"
    check_field "BSR"          "$CSV_BSR"      "$LIVE_BSR"

    # Record row-level updates for top-1000.csv (raw live price for Price Range)
    ROW_P="$_NOCHANGE" ROW_RT="$_NOCHANGE" ROW_RV="$_NOCHANGE"
    if [[ -n "$LIVE_PRICE" && "$CSV_PRICE_N" != "$LIVE_PRICE_N" ]]; then
      ROW_P="$LIVE_PRICE"
    fi
    if [[ -n "$LIVE_RATING" && "$CSV_RATING" != "$LIVE_RATING" ]]; then
      ROW_RT="$LIVE_RATING"
    fi
    if [[ -n "$LIVE_REVIEWS" && "$CSV_REVIEWS" != "$LIVE_REVIEWS" ]]; then
      ROW_RV="$LIVE_REVIEWS"
    fi
    if [[ "$ROW_P" != "$_NOCHANGE" || "$ROW_RT" != "$_NOCHANGE" || "$ROW_RV" != "$_NOCHANGE" ]]; then
      printf '%s\t%s\t%s\t%s\n' "$ASIN" "$ROW_P" "$ROW_RT" "$ROW_RV" >> "$TMP_UPDATES"
    fi

    if [[ "$FOUND_DIFF" == "false" ]]; then
      echo "    ✓ No differences"
    fi
  done

  BATCH_LINES=()
}

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" ]] && continue
  BATCH_LINES+=("$line")

  if [[ ${#BATCH_LINES[@]} -eq $BATCH_SIZE ]]; then
    process_batch
    if [[ $CHECKED -lt $TOTAL ]]; then
      sleep 1
    fi
  fi
done < "$TMP_ROWS"

# Process any remaining rows (last partial batch)
if [[ ${#BATCH_LINES[@]} -gt 0 ]]; then
  process_batch
fi

# ── Merge Price Range, Rating, Review Count into top-1000.csv ────────────────
MERGED_ROWS=0
if [[ -s "$TMP_UPDATES" ]]; then
  MERGED_ROWS=$(python3 - <<PYEOF
import csv
import os
import tempfile

csv_path = r"$CSV_FILE"
updates_path = r"$TMP_UPDATES"
nochange = r"$_NOCHANGE"

by_asin = {}
with open(updates_path, encoding="utf-8", errors="replace", newline="") as uf:
    for line in uf:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        asin, p, rt, rv = parts
        by_asin[asin.strip()] = (p, rt, rv)

if not by_asin:
    print(0)
    raise SystemExit(0)

changed = 0
with open(csv_path, encoding="utf-8-sig", errors="replace", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames or [])
    rows = list(reader)

for row in rows:
    asin = (row.get("ASIN") or "").strip()
    if asin not in by_asin:
        continue
    p, rt, rv = by_asin[asin]
    touched = False
    if p != nochange:
        row["Price Range"] = p
        touched = True
    if rt != nochange:
        row["Rating"] = rt
        touched = True
    if rv != nochange:
        row["Review Count"] = rv
        touched = True
    if touched:
        changed += 1

dir_name = os.path.dirname(csv_path) or "."
fd, tmp_path = tempfile.mkstemp(suffix=".csv", dir=dir_name)
os.close(fd)
try:
    with open(tmp_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, csv_path)
except OSError:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise

print(changed)
PYEOF
)
  echo ""
  echo "Merged live Price Range / Rating / Review Count into: $CSV_FILE ($MERGED_ROWS row(s) updated)."
else
  echo ""
  echo "No Price/Rating/Review Count changes to merge into $CSV_FILE."
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "═════════════════════════════════════════════════════"
echo "Done. Checked $CHECKED products across $BATCH_NUM batches."
echo "Differences found: $DIFF_COUNT"
if [[ $DIFF_COUNT -gt 0 ]]; then
  echo "Review file: $OUTPUT_FILE"
fi
echo "Backup: $BACKUP_FILE"
