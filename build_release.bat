@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Missing .venv\Scripts\python.exe
    echo Create the virtual environment and install requirements-build.txt first.
    pause
    exit /b 1
)

if exist "build\rox_bot" (
    echo [ERROR] build\rox_bot already exists.
    echo Move or remove the old build output before rebuilding.
    pause
    exit /b 1
)

if exist "dist\ROX Bot" (
    echo [ERROR] dist\ROX Bot already exists.
    echo Move or remove the old release folder before rebuilding.
    pause
    exit /b 1
)

if exist "dist\ROX-Bot-Windows.zip" (
    echo [ERROR] dist\ROX-Bot-Windows.zip already exists.
    echo Move or remove the old archive before rebuilding.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m PyInstaller --workpath "build\rox_bot" rox_bot.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

copy "bot.bat" "dist\ROX Bot\bot.bat" >nul
if errorlevel 1 (
    echo [ERROR] Failed to copy bot.bat into the release folder.
    pause
    exit /b 1
)

powershell.exe -NoProfile -Command "$ErrorActionPreference = 'Stop'; Start-Sleep -Seconds 3; Compress-Archive -LiteralPath 'dist\ROX Bot' -DestinationPath 'dist\ROX-Bot-Windows.zip'"
if errorlevel 1 (
    echo [ERROR] Failed to create the release archive.
    pause
    exit /b 1
)

echo.
echo Release ready:
echo   dist\ROX Bot\
echo   dist\ROX-Bot-Windows.zip
pause
