# NYPD Contract Monitor - Windows Installer
# Run: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"
$InstallDir = "$env:LOCALAPPDATA\NYPDContractMonitor"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  NYPD Contract Monitor - Installer" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check for Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python not found. Installing via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        Write-Host "ERROR: Python installation failed. Please install Python 3.11+ manually from python.org" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Python found: $($python.Source)" -ForegroundColor Green

# Check for Node.js
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "Node.js not found. Installing via winget..." -ForegroundColor Yellow
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        Write-Host "ERROR: Node.js installation failed. Please install Node.js LTS manually from nodejs.org" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Node.js found: $($node.Source)" -ForegroundColor Green

# Create install directory
Write-Host ""
Write-Host "Installing to: $InstallDir" -ForegroundColor Yellow
if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
}
New-Item -ItemType Directory -Path $InstallDir | Out-Null

# Copy project files
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Write-Host "Copying files..." -ForegroundColor Yellow
Copy-Item "$ProjectDir\pyproject.toml" "$InstallDir\"
Copy-Item "$ProjectDir\contractmonitor" "$InstallDir\contractmonitor" -Recurse
Copy-Item "$ProjectDir\frontend" "$InstallDir\frontend" -Recurse
Copy-Item "$ProjectDir\.env.example" "$InstallDir\.env.example"

# Create virtual environment
Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
python -m venv "$InstallDir\venv"
& "$InstallDir\venv\Scripts\python.exe" -m pip install --upgrade pip -q

# Install Python deps
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
& "$InstallDir\venv\Scripts\pip.exe" install "$InstallDir" -q

# Install Playwright browser
Write-Host "Installing Chromium browser for PASSPort scanning..." -ForegroundColor Yellow
& "$InstallDir\venv\Scripts\playwright.exe" install chromium

# Build frontend
Write-Host "Building web dashboard..." -ForegroundColor Yellow
Push-Location "$InstallDir\frontend"
npm install --silent 2>$null
npm run build 2>$null
Pop-Location

# Create .env if not exists
if (-not (Test-Path "$InstallDir\.env")) {
    Copy-Item "$InstallDir\.env.example" "$InstallDir\.env"
    Write-Host ""
    Write-Host "Created .env config file. Edit it to configure email notifications:" -ForegroundColor Yellow
    Write-Host "  $InstallDir\.env" -ForegroundColor White
}

# Create run script
$RunScript = @"
@echo off
title NYPD Contract Monitor
echo =====================================
echo   NYPD Contract Monitor
echo   Dashboard: http://localhost:8200
echo   Press Ctrl+C to stop
echo =====================================
echo.
start http://localhost:8200
"$InstallDir\venv\Scripts\contract-monitor.exe" --serve --port 8200
pause
"@
Set-Content -Path "$InstallDir\run.bat" -Value $RunScript

# Create desktop shortcut
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\NYPD Contract Monitor.lnk")
$Shortcut.TargetPath = "$InstallDir\run.bat"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "NYPD Contract Monitor Dashboard"
$Shortcut.Save()

# Create Windows Task Scheduler entry (optional background service)
$CreateTask = Read-Host "Create a scheduled task to run on login? (y/n)"
if ($CreateTask -eq 'y') {
    $Action = New-ScheduledTaskAction -Execute "$InstallDir\venv\Scripts\contract-monitor.exe" -Argument "--serve --port 8200" -WorkingDirectory $InstallDir
    $Trigger = New-ScheduledTaskTrigger -AtLogOn
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName "NYPD Contract Monitor" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Monitors NYC contract sites for NYPD contracts" -Force
    Write-Host "Scheduled task created - will start on login" -ForegroundColor Green
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start: double-click 'NYPD Contract Monitor' on your Desktop" -ForegroundColor White
Write-Host "Dashboard: http://localhost:8200" -ForegroundColor White
Write-Host ""
Write-Host "Config file: $InstallDir\.env" -ForegroundColor Gray
Write-Host "  - Set SMTP_* vars for email alerts" -ForegroundColor Gray
Write-Host "  - Set SAM_API_KEY for federal contracts" -ForegroundColor Gray
Write-Host "  - Set LLM_BASE_URL if using a local LLM" -ForegroundColor Gray
Write-Host ""

$StartNow = Read-Host "Start the monitor now? (y/n)"
if ($StartNow -eq 'y') {
    Start-Process "$InstallDir\run.bat"
}
