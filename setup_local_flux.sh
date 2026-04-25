#!/usr/bin/env bash
# Thin wrapper: real install lives in scripts/bootstrap_flux_venv.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$REPO_ROOT/scripts/bootstrap_flux_venv.sh"
