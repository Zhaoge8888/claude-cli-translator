$ErrorActionPreference = "Continue"

$processes = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*hotkey-double-ctrl.py*" }
if (-not $processes) {
    Write-Host "No Python hotkey process found."
    exit 0
}

foreach ($process in $processes) {
    Write-Host "Stopping hotkey process $($process.ProcessId)..."
    Stop-Process -Id $process.ProcessId -Force
}

