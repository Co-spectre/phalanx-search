@echo off
title Phalanx Search - Desktop App
echo.
echo ==========================================
echo    PHALANX SEARCH - Desktop Application
echo ==========================================
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the desktop application
python run_desktop.py

pause
