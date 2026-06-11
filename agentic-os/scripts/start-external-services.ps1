# Start Mission Control external services (Hermes Dashboard, Pipeline UI, Deal Poster)
$ErrorActionPreference = "Stop"
$WslRepo = "/mnt/e/GITHUB/hotproductsdot-v2"
Write-Host "Starting external services..." -ForegroundColor Cyan
wsl bash -lc "bash '$WslRepo/agentic-os/scripts/start-external-services.sh'"
