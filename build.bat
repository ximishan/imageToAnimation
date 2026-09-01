@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip
pip install -r requirements.txt

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
