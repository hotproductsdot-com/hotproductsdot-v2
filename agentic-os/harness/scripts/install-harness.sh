#!/usr/bin/env bash
# Install portfolio harness — run from any project or hotproductsdot-v2 root
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HARNESS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="$(cd "$HARNESS_DIR/../.." && pwd)"

usage() {
  echo "Usage: $0 [--all | --project PATH] [--merge] [--dry-run]"
  exit 1
}

ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all|--merge|--dry-run|--skip-cursor|--skip-registry)
      ARGS+=("$1")
      shift
      ;;
    --project)
      ARGS+=("$1" "$2")
      shift 2
      ;;
    -h|--help) usage ;;
    *) ARGS+=(--project "$1"); shift ;;
  esac
done

cd "$REPO"
python3 "$HARNESS_DIR/install.py" "${ARGS[@]}"
