@echo off
chcp 65001 >nul
setlocal

set "BASEDIR=%~dp0"
set "TASKNAME=flex-commute-bot"

echo =========================================
echo   flex-commute-bot 자동 시작 등록
echo =========================================
echo.

:: 관리자 권한 확인
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 관리자 권한으로 실행해주세요.
    echo 이 파일을 우클릭 후 "관리자 권한으로 실행" 선택
    pause
    exit /b 1
)

:: 기존 작업 삭제 (있으면)
schtasks /delete /tn "%TASKNAME%" /f >nul 2>&1

:: 작업 스케줄러 등록 (로그온 시 실행, 최고 권한)
schtasks /create ^
  /tn "%TASKNAME%" ^
  /tr "\"%BASEDIR%start.bat\"" ^
  /sc onlogon ^
  /rl highest ^
  /f >nul

if errorlevel 1 (
    echo [ERROR] 작업 등록 실패
    pause
    exit /b 1
)

echo [OK] 자동 시작 등록 완료!
echo.
echo  - 작업 이름: %TASKNAME%
echo  - 실행 시점: Windows 로그온 시
echo  - 로그 파일: %BASEDIR%logs\output.log
echo.
echo 등록 제거하려면 remove-autostart.bat 실행
echo =========================================
pause
endlocal
