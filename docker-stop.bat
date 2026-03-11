@echo off
chcp 65001 >nul
setlocal
set "BASEDIR=%~dp0"

echo 봇을 종료합니다...
cd /d "%BASEDIR%"
docker compose down
echo.
echo [OK] 종료 완료.
timeout /t 2 >nul
endlocal
