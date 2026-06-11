# Install Agentic OS via WSL (Hermes runs in WSL on this machine)
$ErrorActionPreference = "Stop"
$Repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$WslRepo = "/mnt/e/GITHUB/hotproductsdot-v2"

Write-Host "Installing Agentic OS via WSL..." -ForegroundColor Cyan
wsl -e bash -lc "cd '$WslRepo' && bash agentic-os/scripts/install.sh"

Write-Host "`nStarting external services..." -ForegroundColor Cyan
wsl bash -lc "bash '$WslRepo/agentic-os/scripts/start-external-services.sh'"

Write-Host "`nRestarting Mission Control..." -ForegroundColor Cyan
Start-Process wsl -ArgumentList "-e", "bash", "-lc", "cd '$WslRepo' && fuser -k 9120/tcp 2>/dev/null; pkill -f mission-control/server.py 2>/dev/null; sleep 1; nohup python3 agentic-os/mission-control/server.py > /tmp/mc.log 2>&1 &" -WindowStyle Minimized

Write-Host "`nMission Control: http://127.0.0.1:9120" -ForegroundColor Green
Write-Host "  Sub-pages: /hermes  /pantheon  /bridge  /memory  /growth  /cron  /skills" -ForegroundColor Gray
Write-Host "Hermes Dashboard: http://127.0.0.1:9119  (run: wsl hermes dashboard --tui)" -ForegroundColor Green
