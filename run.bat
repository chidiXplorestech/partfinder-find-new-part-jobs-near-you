@echo off
REM PartFinder — one-click launcher for Windows. Double-click this file.
cd /d "%~dp0"

echo Installing dependencies (first run only)...
python -m pip install -q -r requirements.txt

echo Starting PartFinder...
python server.py

echo.
echo PartFinder stopped. Press any key to close.
pause >nul
