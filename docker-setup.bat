@echo off
chcp 65001 >nul
setlocal
set "BASEDIR=%~dp0"

echo =========================================
echo   flex-slack-monitor Docker 설치
echo =========================================
echo.

:: Docker 설치 확인
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker가 설치되지 않았습니다.
    echo.
    echo Docker Desktop을 설치하세요:
    echo https://www.docker.com/products/docker-desktop/
    echo.
    echo 설치 후 Docker Desktop을 실행하고 다시 시도하세요.
    pause
    exit /b 1
)

echo [OK] Docker 확인 완료
docker --version
echo.

:: Docker 실행 중인지 확인
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop이 실행되지 않았습니다.
    echo Docker Desktop을 먼저 실행하고 다시 시도하세요.
    pause
    exit /b 1
)

echo [OK] Docker Desktop 실행 중
echo.

:: .env 파일 확인
if not exist "%BASEDIR%.env" (
    echo [ERROR] .env 파일이 없습니다.
    echo .env.example을 복사하여 .env를 만들고 SLACK_BOT_TOKEN을 설정하세요.
    pause
    exit /b 1
)
echo [OK] .env 파일 확인
echo.

:: 필요 디렉토리 생성
if not exist "%BASEDIR%auth" mkdir "%BASEDIR%auth"
if not exist "%BASEDIR%data" mkdir "%BASEDIR%data"
if not exist "%BASEDIR%logs" mkdir "%BASEDIR%logs"

:: session.json 확인
if not exist "%BASEDIR%auth\session.json" (
    echo [WARN] auth\session.json 이 없습니다.
    echo.
    echo Flex 로그인이 필요합니다. login.bat을 실행하세요.
    echo 로그인 후 docker-start.bat을 실행하면 됩니다.
    echo.
    pause
    exit /b 1
)
echo [OK] session.json 확인
echo.

:: 이미지 빌드
echo [빌드 중] Docker 이미지 빌드... (최초 실행 시 5~10분 소요)
echo.
cd /d "%BASEDIR%"
docker compose build
if errorlevel 1 (
    echo.
    echo [ERROR] 빌드 실패. 위 오류 메시지를 확인하세요.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   설치 완료!
echo   docker-start.bat 으로 시작하세요.
echo =========================================
pause
endlocal
