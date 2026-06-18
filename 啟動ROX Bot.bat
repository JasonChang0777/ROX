@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo [ERROR] Missing .venv\Scripts\pythonw.exe
    echo Please create the ROX virtual environment and install requirements first.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" ".\rox_gardening\rox_bot_launcher.pyw"
