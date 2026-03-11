@echo off
echo =========================================
echo   flex-commute-bot install
echo =========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed.
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [1/4] Python OK
python --version

if not exist ".env" (
    echo.
    echo [ERROR] .env file not found.
    echo Copy .env.example to .env and set SLACK_BOT_TOKEN.
    pause
    exit /b 1
)

echo [2/4] .env OK

echo.
echo [3/4] Installing packages... (may take a few minutes)
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package install failed.
    pause
    exit /b 1
)

echo.
echo [4/4] Installing Playwright browser... (may take a few minutes)
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Playwright install failed.
    pause
    exit /b 1
)

if not exist "logs" mkdir logs
if not exist "auth" mkdir auth

echo.
echo =========================================
echo   Install complete!
echo   Next: run login.bat to log in to Flex
echo =========================================
pause
