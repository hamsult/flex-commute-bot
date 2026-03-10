@echo off
chcp 65001 >nul
echo ========================================
echo   Flex 로그인 (세션 생성)
echo ========================================
echo.
echo 브라우저가 열립니다. Flex에 로그인하세요.
echo 로그인 완료 후 브라우저를 닫으면 세션이 저장됩니다.
echo.

python src\auth_setup.py

if errorlevel 1 (
    echo.
    echo [오류] 로그인 실패. 다시 시도하세요.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   로그인 완료! 이제 start.bat 을 실행하세요.
echo ========================================
pause
