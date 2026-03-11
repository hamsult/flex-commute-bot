@echo off
chcp 65001 >nul

set "TASKNAME=flex-commute-bot"

echo 자동 시작 등록 제거 중...

net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 관리자 권한으로 실행해주세요.
    pause
    exit /b 1
)

schtasks /delete /tn "%TASKNAME%" /f >nul 2>&1
if errorlevel 1 (
    echo [INFO] 등록된 작업이 없습니다.
) else (
    echo [OK] 자동 시작 제거 완료
)
pause
