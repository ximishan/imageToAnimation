@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo ImageToAnimation - Local Run
 echo ============================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python 3.11 and make sure "python" is available.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment with the active Python...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] pip initialization failed.
    pause
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

if not exist "bin\ffmpeg.exe" (
    echo [INFO] FFmpeg not found. Downloading...
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\download_ffmpeg.ps1"
    if errorlevel 1 (
        echo [ERROR] FFmpeg download failed.
        pause
        exit /b 1
    )
)

echo [INFO] Starting ImageToAnimation...
echo.
python app.py
set "EXITCODE=%ERRORLEVEL%"

echo.
echo ============================================
if not "%EXITCODE%"=="0" (
    echo [ERROR] Application exited with code %EXITCODE%.
    echo Run this script from a terminal to see the traceback above.
) else (
    echo [INFO] Application closed normally.
)
echo ============================================
pause
exit /b %EXITCODE%
