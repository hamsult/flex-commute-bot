@echo off
chcp 65001 >nul

:: auth/session.json 확인
if not exist "auth\session.json" (
    echo [오류] 로그인이 필요합니다. login.bat 을 먼저 실행하세요.
    pause
    exit /b 1
)

:: .env 확인
if not exist ".env" (
    echo [오류] .env 파일이 없습니다. SLACK_BOT_TOKEN 을 설정하세요.
    pause
    exit /b 1
)

:: logs 폴더 생성
if not exist "logs" mkdir logs

echo flex-commute-bot 시작 중...
echo 로그: logs\output.log
echo 종료하려면 stop.bat 을 실행하세요.

:: 백그라운드 실행 (터미널 창 숨김)
start /min "" python src\main.py >> logs\output.log 2>&1

echo.
echo 봇이 백그라운드에서 실행 중입니다.
timeout /t 3 >nul
