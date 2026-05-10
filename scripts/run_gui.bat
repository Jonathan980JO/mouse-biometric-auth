@echo off
REM Quick launcher for Mouse Auth GUI
REM Double-click this file to start the application

echo.
echo ======================================
echo   Mouse Dynamics Authentication GUI
echo ======================================
echo.
echo Starting application...
echo.

REM Navigate to project root
cd /d %~dp0..

REM Activate conda environment (optional)
call conda activate mouse 2>nul

REM Run the main GUI application
python src/MouseAuth.py

pause
