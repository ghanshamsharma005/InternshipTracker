@echo off
echo =========================================================
echo       Starting InternTrack Management System...
echo =========================================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b 1
)

REM Install required packages if needed
echo Checking dependencies...
pip install -r requirements.txt

REM Launch Application
echo.
echo Starting Flask Application on http://localhost:5000 ...
echo Press Ctrl+C to stop the server.
echo.
python app.py
pause
