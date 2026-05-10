@echo off
REM Quick test script to verify GUI application works
REM Run this before demo day to ensure everything is ready

echo.
echo ========================================
echo   MOUSE AUTH GUI - PRE-DEMO TEST
echo ========================================
echo.

REM Check conda environment
echo [1/5] Checking conda environment...
call conda activate mouse
if errorlevel 1 (
    echo ❌ ERROR: Could not activate 'mouse' environment
    echo Please create environment first
    pause
    exit /b 1
)
echo ✅ Environment activated

REM Check Python packages
echo.
echo [2/5] Checking Python packages...
python -c "import tkinter; import pandas; import numpy; import sklearn; import xgboost; print('✅ All packages installed')"
if errorlevel 1 (
    echo ❌ ERROR: Missing packages
    pause
    exit /b 1
)

REM Check backend files exist
echo.
echo [3/5] Checking backend files...
if not exist "feature_extractor.py" (
    echo ❌ ERROR: feature_extractor.py not found
    pause
    exit /b 1
)
if not exist "incremental_enroll.py" (
    echo ❌ ERROR: incremental_enroll.py not found
    pause
    exit /b 1
)
if not exist "real_time_auth.py" (
    echo ❌ ERROR: real_time_auth.py not found
    pause
    exit /b 1
)
if not exist "mouse_auth_app.py" (
    echo ❌ ERROR: mouse_auth_app.py not found
    pause
    exit /b 1
)
echo ✅ All backend files exist

REM Check model file
echo.
echo [4/5] Checking model file...
if not exist "mouse_auth_kaggle.pkl" (
    echo ⚠️  WARNING: Model file not found
    echo You need to run: python advanced_training.py
    echo.
    set /p continue="Continue anyway? (y/n): "
    if /i not "%continue%"=="y" (
        pause
        exit /b 1
    )
) else (
    echo ✅ Model file exists
)

REM Test GUI import
echo.
echo [5/5] Testing GUI import...
python -c "import mouse_auth_app; print('✅ GUI application ready')"
if errorlevel 1 (
    echo ❌ ERROR: GUI import failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo   ✅ ALL TESTS PASSED!
echo ========================================
echo.
echo Your system is ready for demo.
echo.
echo To launch GUI:
echo   1. Double-click run_gui.bat
echo   2. Or run: python mouse_auth_app.py
echo.
echo Quick test workflow:
echo   Tab 1: Collect 5 sessions for "TestUser"
echo   Tab 2: Enroll "TestUser" (should take ~10s)
echo   Tab 3: Authenticate "TestUser" (should be >85%%)
echo.
pause
