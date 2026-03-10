@echo off
if not exist "auth\session.json" (
    echo [ERROR] Login required. Please run login.bat first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env file not found. Please set SLACK_BOT_TOKEN.
    pause
    exit /b 1
)

if not exist "logs" mkdir logs

echo Starting flex-commute-bot...
echo Log file: logs\output.log
echo To stop: run stop.bat

powershell -WindowStyle Hidden -Command "cd '%~dp0'; python src\main.py >> logs\output.log 2>&1"

echo.
echo Bot is running in the background.
timeout /t 3 >nul
