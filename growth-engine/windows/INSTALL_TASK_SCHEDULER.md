# Installing the Daily Growth Engine on Windows

You have two options.

## Option A — One-line install (recommended)

Right-click PowerShell → **Run as Administrator**, then:

```powershell
cd E:\GITHUB\hotproductsdot-v2\growth-engine\windows
powershell -ExecutionPolicy Bypass -File .\install_task.ps1
```

This registers a scheduled task named `growth-engine-daily` that runs every
morning at 6:00 AM and logs to `growth-engine\data\logs\`.

To trigger manually right now:

```powershell
Start-ScheduledTask -TaskName growth-engine-daily
```

To remove it:

```powershell
Unregister-ScheduledTask -TaskName growth-engine-daily -Confirm:$false
```

## Option B — Manual setup via Task Scheduler GUI

1. Press `Win+R`, type `taskschd.msc`, press Enter.
2. **Action → Create Basic Task...**
3. Name: `growth-engine-daily` · Description: `Daily content + visibility run`
4. Trigger: **Daily**, time: 6:00 AM (or whenever).
5. Action: **Start a program**.
   - Program/script: `E:\GITHUB\hotproductsdot-v2\growth-engine\windows\run_daily.bat`
6. Finish.
7. Right-click the task → **Properties** → check
   *Run whether user is logged on or not* and *Run with highest privileges*.

## Verifying

After install, run the bat once by hand to make sure your Python and
ANTHROPIC_API_KEY are set up correctly:

```powershell
E:\GITHUB\hotproductsdot-v2\growth-engine\windows\run_daily.bat
```

Then check the latest log file:

```powershell
Get-ChildItem E:\GITHUB\hotproductsdot-v2\growth-engine\data\logs |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

## Troubleshooting

| Symptom                                    | Fix                                                         |
|--------------------------------------------|-------------------------------------------------------------|
| "python is not recognized"                 | Add Python to PATH or edit run_daily.bat to call python.exe by full path |
| ANTHROPIC_API_KEY not found                | Confirm it's in `E:\GITHUB\hotproductsdot-v2\.env`          |
| `git push` rejected                        | Pre-set up SSH keys for GitHub on this machine              |
| `npm run deploy:rsync` fails               | Make sure your `hotproducts` SSH host alias is configured   |
| Articles not appearing on the site         | Run `npm run build` in `site/` — confirm guides.ts loader merged |
