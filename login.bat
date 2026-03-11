@echo off
chcp 65001 >nul
setlocal
set "BASEDIR=%~dp0"

echo =========================================
echo   Flex 로그인 (세션 갱신)
echo =========================================
echo.
echo 브라우저가 열립니다. Flex에 로그인 후
echo 이 창에서 Enter를 누르세요.
echo.

:: Python 설치 확인 (로그인은 로컬 Python으로 실행)
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python이 설치되지 않았습니다.
    echo https://python.org 에서 설치하세요.
    pause
    exit /b 1
)

:: playwright 설치 확인
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo [INFO] playwright 설치 중...
    pip install playwright >nul 2>&1
    python -m playwright install chromium
)

cd /d "%BASEDIR%"
python src\auth_setup.py

if errorlevel 1 (
    echo.
    echo [ERROR] 로그인 실패. 다시 시도하세요.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   로그인 완료!
echo.
echo   봇이 실행 중이면 docker-start.bat 으로
echo   재시작하여 새 세션을 적용하세요.
echo =========================================
pause
endlocal
