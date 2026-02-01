@echo off
echo.
echo ============================================================
echo    PHALANX SEARCH - Installation Script
echo ============================================================
echo.

cd /d "%~dp0"

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.9+
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo Creating virtual environment...
python -m venv venv

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing dependencies (this may take a few minutes)...
echo.
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ============================================================
echo    Installation Complete!
echo ============================================================
echo.
echo To start Phalanx Search:
echo    1. Double-click START.bat
echo    2. Or run: python run.py
echo.
echo The first run will download the AI model (~90MB)
echo This only happens once and runs 100%% locally.
echo.

pause
