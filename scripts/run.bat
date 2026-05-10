@echo off
REM Mouse Biometric Authentication System launcher
REM Navigate to project root and run the main GUI application

cd /d %~dp0..
echo Starting Mouse Biometric Authentication System...
echo.

python src/MouseAuth.py

echo.
echo Application closed.
pause
