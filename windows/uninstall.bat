@echo off
echo Uninstalling NYPD Contract Monitor...
echo.

:: Stop any running instances
taskkill /F /IM contract-monitor.exe 2>nul

:: Remove scheduled task
schtasks /Delete /TN "NYPD Contract Monitor" /F 2>nul

:: Remove install directory
rmdir /S /Q "%LOCALAPPDATA%\NYPDContractMonitor" 2>nul

:: Remove desktop shortcut
del "%USERPROFILE%\Desktop\NYPD Contract Monitor.lnk" 2>nul

echo.
echo Uninstalled successfully.
pause
