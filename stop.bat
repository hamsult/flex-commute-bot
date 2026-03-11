@echo off
chcp 65001 >nul
setlocal

set "BASEDIR=%~dp0"
set "PIDFILE=%BASEDIR%data\bot.pid"

if not exist "%PIDFILE%" (
    echo [INFO] No PID file found. Bot may not be running.
    pause
    exit /b 0
)

set /p PID=<"%PIDFILE%"

echo Stopping flex-commute-bot ^(PID %PID%^)...
taskkill /pid %PID% /f >nul 2>&1

if errorlevel 1 (
    echo [WARN] Process not found. Already stopped.
) else (
    echo Bot stopped.
)

del "%PIDFILE%"
timeout /t 2 >nul
endlocal
