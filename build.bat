@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo ImageToAnimation - Windows Build
 echo ============================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo The GitHub Actions workflow uses Python 3.11.
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
if errorlevel 1 exit /b 1

pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist "bin\ffmpeg.exe" (
    echo [INFO] FFmpeg not found. Downloading...
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\download_ffmpeg.ps1"
    if errorlevel 1 exit /b 1
)

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

pyinstaller --noconfirm ImageToAnimation.spec
if errorlevel 1 exit /b 1

if not exist "dist\ImageToAnimation\bin" mkdir "dist\ImageToAnimation\bin"
copy /y "bin\ffmpeg.exe" "dist\ImageToAnimation\bin\ffmpeg.exe" >nul
if exist "bin\ffprobe.exe" copy /y "bin\ffprobe.exe" "dist\ImageToAnimation\bin\ffprobe.exe" >nul

echo.
echo ============================================
echo Build complete:
echo dist\ImageToAnimation\ImageToAnimation.exe
echo ============================================
