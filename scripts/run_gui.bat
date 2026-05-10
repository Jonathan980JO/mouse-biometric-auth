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

REM Activate conda environment
call conda activate mouse

REM Run the Quick Authentication
python quick_auth.py

pause
