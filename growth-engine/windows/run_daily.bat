@echo off
REM growth-engine daily run for Windows Task Scheduler.
REM Update PROJECT_DIR if you cloned the repo elsewhere.

set PROJECT_DIR=E:\GITHUB\hotproductsdot-v2
set ENGINE_DIR=%PROJECT_DIR%\growth-engine
set LOG_DIR=%ENGINE_DIR%\data\logs

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set TIMESTAMP=%DATE:~10,4%-%DATE:~4,2%-%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOG_FILE=%LOG_DIR%\run_%TIMESTAMP%.log

cd /d "%PROJECT_DIR%"

echo === growth-engine run started %DATE% %TIME% === >> "%LOG_FILE%"
python "%ENGINE_DIR%\scripts\run_daily.py" >> "%LOG_FILE%" 2>&1
echo === exit code: %ERRORLEVEL% === >> "%LOG_FILE%"

exit /b %ERRORLEVEL%
