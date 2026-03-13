@echo off
chcp 65001 >nul
setlocal

set "BASEDIR=%~dp0"
set "PIDFILE=%BASEDIR%data\bot.pid"
set "LOGFILE=%BASEDIR%logs\output.log"

:: 이미 실행 중인지 확인
if exist "%PIDFILE%" (
    set /p OLDPID=<"%PIDFILE%"
    tasklist /fi "PID eq %OLDPID%" /fo csv 2>nul | find "python" >nul
    if not errorlevel 1 (
        echo [INFO] Bot is already running ^(PID %OLDPID%^). Run stop.bat first.
        pause
        exit /b 0
    )
    del "%PIDFILE%"
)

:: 필수 파일 확인
if not exist "%BASEDIR%auth\session.json" (
    echo [ERROR] Login required. Please run login.bat first.
    pause
    exit /b 1
)

if not exist "%BASEDIR%.env" (
    echo [ERROR] .env file not found. Please set SLACK_BOT_TOKEN.
    pause
    exit /b 1
)

if not exist "%BASEDIR%logs" mkdir "%BASEDIR%logs"
if not exist "%BASEDIR%data" mkdir "%BASEDIR%data"

echo Starting flex-commute-bot...
echo Log: %LOGFILE%
echo.

set "ERRFILE=%BASEDIR%logs\error.log"

:: 백그라운드 실행 후 PID 저장
powershell -NoProfile -Command "$p = Start-Process python -ArgumentList 'src\main.py' -WorkingDirectory '%BASEDIR%' -WindowStyle Hidden -PassThru -RedirectStandardOutput '%LOGFILE%' -RedirectStandardError '%ERRFILE%'; $p.Id | Out-File -Encoding ascii '%PIDFILE%'; Write-Host ('Bot started. PID=' + $p.Id)"

echo.
echo Run stop.bat to stop the bot.
timeout /t 2 >nul
endlocal
