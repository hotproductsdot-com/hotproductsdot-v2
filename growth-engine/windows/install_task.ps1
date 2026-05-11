# growth-engine - register 3 daily runs as Windows Scheduled Tasks.
# Runs at 7 AM, 12 PM, and 6 PM - one article per run.
# Run from an elevated PowerShell prompt:
#   powershell -ExecutionPolicy Bypass -File install_task.ps1

$BatPath = "E:\GITHUB\hotproductsdot-v2\growth-engine\windows\run_daily.bat"

if (-not (Test-Path $BatPath)) {
    Write-Error "Bat script not found at $BatPath"
    exit 1
}

$tasks = @(
    @{ Name = "growth-engine-morning"; Hour = 7;  Label = "7:00 AM"  },
    @{ Name = "growth-engine-noon";    Hour = 12; Label = "12:00 PM" },
    @{ Name = "growth-engine-evening"; Hour = 18; Label = "6:00 PM"  }
)

# Also remove the old single-task name if it exists
foreach ($old in @("growth-engine-daily")) {
    $existing = Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Removing old task '$old'..."
        Unregister-ScheduledTask -TaskName $old -Confirm:$false
    }
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType S4U -RunLevel Highest

foreach ($task in $tasks) {
    $existing = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Removing existing task '$($task.Name)'..."
        Unregister-ScheduledTask -TaskName $task.Name -Confirm:$false
    }

    $action  = New-ScheduledTaskAction -Execute $BatPath
    $trigger = New-ScheduledTaskTrigger -Daily -At "$($task.Hour):00"

    Register-ScheduledTask -TaskName $task.Name `
        -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
        -Description "hotproductsdot.com growth engine - $($task.Label) run."

    Write-Host "Installed '$($task.Name)' -> runs daily at $($task.Label)."
}

Write-Host ""
Write-Host "3 tasks registered: morning (7 AM), noon (12 PM), evening (6 PM)."
Write-Host "Trigger now: Start-ScheduledTask -TaskName growth-engine-morning"
