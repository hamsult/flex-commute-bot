@echo off
chcp 65001 >nul
echo ========================================
echo   flex-commute-bot 설치 시작
echo ========================================
echo.

:: Python 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://python.org 에서 Python을 설치한 후 다시 실행하세요.
    echo 설치 시 "Add Python to PATH" 를 반드시 체크하세요.
    pause
    exit /b 1
)

echo [1/3] Python 확인 완료
python --version

:: .env 파일 확인
if not exist ".env" (
    echo.
    echo [오류] .env 파일이 없습니다.
    echo .env.example 파일을 복사해서 .env 로 이름 바꾸고
    echo SLACK_BOT_TOKEN 값을 입력한 후 다시 실행하세요.
    pause
    exit /b 1
)

echo [2/3] .env 파일 확인 완료

:: 패키지 설치
echo.
echo [3/3] 패키지 설치 중... (수 분 소요)
pip install -r requirements.txt
if errorlevel 1 (
    echo [오류] 패키지 설치 실패
    pause
    exit /b 1
)

:: Playwright Chromium 설치
echo.
echo [4/4] Playwright 브라우저 설치 중... (수 분 소요)
playwright install chromium
if errorlevel 1 (
    echo [오류] Playwright 브라우저 설치 실패
    pause
    exit /b 1
)

:: logs 폴더 생성
if not exist "logs" mkdir logs

:: auth 폴더 생성
if not exist "auth" mkdir auth

echo.
echo ========================================
echo   설치 완료!
echo   다음 단계: login.bat 실행 후 Flex 로그인
echo ========================================
pause
