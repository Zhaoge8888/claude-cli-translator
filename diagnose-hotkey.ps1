$ErrorActionPreference = "Continue"

$stateDir = Join-Path $env:LOCALAPPDATA "ClaudeCliTranslator"
$requestDir = Join-Path $stateDir "requests"
$logFile = Join-Path $stateDir "hotkey.log"

Write-Host "State dir: $stateDir"
Write-Host "Request dir exists: $(Test-Path $requestDir)"
Write-Host "Hotkey log exists: $(Test-Path $logFile)"
Write-Host ""

Write-Host "Windows Terminal settings:"
$terminalSettingsPaths = @(
    (Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"),
    (Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe\LocalState\settings.json"),
    (Join-Path $env:LOCALAPPDATA "Microsoft\Windows Terminal\settings.json")
)
$foundTerminalSettings = $false
foreach ($settingsPath in $terminalSettingsPaths) {
    if (Test-Path $settingsPath) {
        $foundTerminalSettings = $true
        try {
            $settings = Get-Content -Raw -Encoding UTF8 $settingsPath | ConvertFrom-Json
            Write-Host "  $settingsPath"
            Write-Host "    copyOnSelect: $($settings.copyOnSelect)"
            Write-Host "    copyFormatting: $($settings.copyFormatting)"
        } catch {
            Write-Host "  $settingsPath"
            Write-Host "    Could not parse settings.json: $($_.Exception.Message)"
        }
    }
}
if (-not $foundTerminalSettings) {
    Write-Host "  No settings.json found."
}
Write-Host ""

Write-Host "AutoHotkey processes:"
$processes = Get-Process | Where-Object { $_.ProcessName -like "AutoHotkey*" }
if ($processes) {
    $processes | Select-Object ProcessName, Id, Path | Format-Table -AutoSize
} else {
    Write-Host "  No AutoHotkey process found."
}

Write-Host ""
Write-Host "Python hotkey processes:"
$pythonHotkeys = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*hotkey-double-ctrl.py*" }
if ($pythonHotkeys) {
    $pythonHotkeys | Select-Object ProcessId, Name, CommandLine | Format-Table -AutoSize -Wrap
} else {
    Write-Host "  No Python hotkey process found."
}

Write-Host ""
Write-Host "Recent hotkey log:"
if (Test-Path $logFile) {
    Get-Content $logFile -Tail 20
} else {
    Write-Host "  No log file yet."
}
