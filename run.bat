@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    py -3 -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist "bin\ffmpeg.exe" (
    echo [INFO] FFmpeg not found. Downloading...
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\download_ffmpeg.ps1"
)

python app.py
