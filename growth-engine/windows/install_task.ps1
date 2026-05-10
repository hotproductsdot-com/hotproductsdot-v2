# growth-engine — register the daily run as a Windows Scheduled Task.
# Run from an elevated PowerShell prompt:
#   powershell -ExecutionPolicy Bypass -File install_task.ps1

$TaskName = "growth-engine-daily"
$BatPath = "E:\GITHUB\hotproductsdot-v2\growth-engine\windows\run_daily.bat"
$RunHour = 6   # 6 AM local

if (-not (Test-Path $BatPath)) {
    Write-Error "Bat script not found at $BatPath"
    exit 1
}

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task $TaskName..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute $BatPath
$trigger = New-ScheduledTaskTrigger -Daily -At "$($RunHour):00AM"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType S4U -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Daily run of the hotproductsdot.com growth engine."

Write-Host ""
Write-Host "Installed scheduled task '$TaskName' to run daily at ${RunHour}:00 AM."
Write-Host "View with:   Get-ScheduledTask -TaskName $TaskName"
Write-Host "Trigger now: Start-ScheduledTask -TaskName $TaskName"
