@echo off
chcp 65001 >nul
setlocal
set "BASEDIR=%~dp0"

echo =========================================
echo   실시간 로그 (종료: Ctrl+C)
echo =========================================
cd /d "%BASEDIR%"
docker logs -f --tail=50 flex-slack-monitor
endlocal
