#!/usr/bin/env bash
# Sample Oxylabs realtime request: amazon_product by ASIN (parsed JSON).
# Loads OXYLABS_USERNAME / OXYLABS_PASSWORD from the environment or repo .env
#
# Usage:
#   chmod +x oxylabs-amazon-product.sh
#   ./oxylabs-amazon-product.sh [ASIN] [geo_location]
# Example:
#   ./oxylabs-amazon-product.sh B07FZ8S74R 90210

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

ASIN="${1:-B07FZ8S74R}"
GEO="${2:-90210}"

if [[ ! "$ASIN" =~ ^[A-Z0-9]{10}$ ]]; then
  echo "ASIN must be 10 alphanumeric characters (e.g. B07FZ8S74R)." >&2
  exit 1
fi

curl 'https://realtime.oxylabs.io/v1/queries' \
  --user "${OXYLABS_USERNAME}:${OXYLABS_PASSWORD}" \
  -H "Content-Type: application/json" \
  -d "{
        \"source\": \"amazon_product\",
        \"query\": \"${ASIN}\",
        \"geo_location\": \"${GEO}\",
        \"parse\": true
    }"

echo
