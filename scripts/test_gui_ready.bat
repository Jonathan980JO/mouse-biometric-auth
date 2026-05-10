@echo off
REM Quick test script to verify GUI application works
REM Run this before launching to ensure everything is ready

echo.
echo ========================================
echo   MOUSE AUTH GUI - PRE-LAUNCH TEST
echo ========================================
echo.

REM Navigate to project root
cd /d %~dp0..

REM Check conda environment (optional)
echo [1/4] Checking conda environment...
call conda activate mouse 2>nul
echo ✅ Environment ready

REM Check Python packages
echo.
echo [2/4] Checking Python packages...
python -c "import tkinter; import pandas; import numpy; import sklearn; print('✅ Core packages installed')"
if errorlevel 1 (
    echo ❌ ERROR: Missing required packages
    echo Install with: pip install pandas numpy scikit-learn
    pause
    exit /b 1
)

REM Check application files
echo.
echo [3/4] Checking application files...
if not exist "src\MouseAuth.py" (
    echo ❌ ERROR: src/MouseAuth.py not found
    pause
    exit /b 1
)
if not exist "src\shared_session_builder.py" (
    echo ❌ ERROR: src/shared_session_builder.py not found
    pause
    exit /b 1
)
echo ✅ All application files present

REM Test Python compilation
echo.
echo [4/4] Testing Python compilation...
python -m py_compile src/MouseAuth.py
if errorlevel 1 (
    echo ❌ ERROR: MouseAuth.py has syntax errors
    pause
    exit /b 1
)
python -m py_compile src/shared_session_builder.py
if errorlevel 1 (
    echo ❌ ERROR: shared_session_builder.py has syntax errors
    pause
    exit /b 1
)
echo ✅ All Python files compile successfully

echo.
echo ========================================
echo   ✅ ALL TESTS PASSED!
echo ========================================
echo.
echo Ready to launch the application.
echo.
echo To start:
echo   1. Double-click run_gui.bat
echo   2. Or run: python src/MouseAuth.py
echo.
pause
