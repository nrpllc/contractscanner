@echo off
echo =====================================
echo   NYPD Contract Monitor - Installer
echo =====================================
echo.
echo This will install the NYPD Contract Monitor.
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 (
    echo.
    echo Installation failed. See errors above.
    pause
    exit /b 1
)
pause
