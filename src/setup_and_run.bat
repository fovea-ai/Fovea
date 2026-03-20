@echo off
cd /d "%~dp0"
echo ============================================
echo   Fovea v2.0 - Setup
echo ============================================
echo.
echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install from https://python.org — check "Add Python to PATH"
    pause & exit /b 1
)

echo Installing required packages...
echo (This may take a minute on first run)
echo.

:: Uninstall headless opencv first - it strips FFmpeg/RTSP support
python -m pip uninstall opencv-python-headless -y >nul 2>&1

:: Install full opencv with FFmpeg - required for RTSP camera support
python -m pip install opencv-python requests cryptography plyer --quiet
python -m pip install PyQt6 --quiet

if errorlevel 1 (
    echo ERROR: Package install failed. Check internet connection.
    pause & exit /b 1
)

echo.
echo Setup complete! Starting Fovea...
echo.
python main.py
if errorlevel 1 ( echo. & echo An error occurred. & pause )