@echo off
chcp 65001 >nul
setlocal
set "BASEDIR=%~dp0"

echo =========================================
echo   flex-slack-monitor 시작
echo =========================================
echo.

:: Docker 실행 확인
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop이 실행되지 않았습니다.
    echo Docker Desktop을 먼저 실행하고 다시 시도하세요.
    pause
    exit /b 1
)

:: session.json 확인
if not exist "%BASEDIR%auth\session.json" (
    echo [ERROR] auth\session.json 이 없습니다. login.bat을 먼저 실행하세요.
    pause
    exit /b 1
)

cd /d "%BASEDIR%"

:: 이미 실행 중인 컨테이너 확인
docker ps --filter "name=flex-slack-monitor" --format "{{.Names}}" | find "flex-slack-monitor" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] 이미 실행 중입니다. 재시작합니다...
    docker compose restart
    goto :STATUS
)

:: 컨테이너 시작
docker compose up -d
if errorlevel 1 (
    echo.
    echo [ERROR] 시작 실패. docker-setup.bat을 먼저 실행했는지 확인하세요.
    pause
    exit /b 1
)

:STATUS
echo.
echo [OK] 봇이 실행 중입니다.
echo.
echo 로그 확인: docker-logs.bat
echo 종료:     docker-stop.bat
echo.
timeout /t 3 >nul
endlocal
