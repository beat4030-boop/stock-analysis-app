@echo off
chcp 65001 >nul
title 키움증권 자동매매 시스템

echo ========================================
echo   키움증권 자동매매 시스템 시작
echo ========================================
echo.

:: Python 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/ 에서 Python을 설치해주세요.
    echo 설치 시 "Add Python to PATH" 체크 필수!
    pause
    exit /b
)

echo [1/3] Python 패키지 설치 중...
cd /d "%~dp0server"
pip install -r requirements.txt -q

echo [2/3] .env 파일 확인 중...
if not exist ".env" (
    echo [알림] .env 파일이 없습니다. .env.example을 복사합니다.
    copy .env.example .env >nul
    echo.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo   server\.env 파일을 열어서
    echo   APP_KEY, SECRET_KEY, 계좌번호를 입력하세요!
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    notepad .env
    pause
)

echo [3/3] 서버 시작 + 브라우저 열기...
echo.
echo 서버 주소: http://localhost:5000
echo 종료하려면 이 창을 닫으세요.
echo ========================================

:: 2초 후 브라우저에서 trading.html 열기
start "" "cmd /c timeout /t 2 /nobreak >nul && start "" "%~dp0trading.html""

:: 서버 실행 (이 창이 열려 있는 동안 서버 유지)
python app.py
