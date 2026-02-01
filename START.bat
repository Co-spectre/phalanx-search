@echo off
echo.
echo ============================================================
echo    PHALANX SEARCH - Local AI Document Search Engine
echo ============================================================
echo.
echo [Privacy] 100%% Local - No data leaves your system
echo.

cd /d "%~dp0"

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.9+
    pause
    exit /b 1
)

echo.
echo Starting Phalanx Search...
echo.
echo Once loaded, open your browser to: http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo.

python run.py

pause
