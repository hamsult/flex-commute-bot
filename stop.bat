@echo off
chcp 65001 >nul
echo flex-commute-bot 종료 중...

taskkill /f /im python.exe >nul 2>&1

echo 봇이 종료되었습니다.
timeout /t 2 >nul
