@echo off
setlocal
cd /d "%~dp0"

if exist "ROX Bot.exe" (
    start "" "ROX Bot.exe"
    exit /b 0
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" ".\rox_gardening\rox_bot_launcher.pyw"
    exit /b 0
)

echo [ERROR] ROX Bot executable or development environment was not found.
echo Please extract the complete release package before running bot.bat.
pause
exit /b 1
