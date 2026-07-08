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
            $actions = @($settings.actions)
            $keybindings = @($settings.keybindings)
            $translatorCopyAction = $actions | Where-Object { $_.id -eq "User.claudeCliTranslator.copyKeepSelection" } | Select-Object -First 1
            if ($translatorCopyAction) {
                $commandJson = $translatorCopyAction.command | ConvertTo-Json -Compress -Depth 10
                Write-Host "    translator copy action: $commandJson"
            } else {
                Write-Host "    translator copy action: missing"
            }

            foreach ($keys in @("ctrl+c", "ctrl+shift+c", "ctrl+space")) {
                $binding = $keybindings | Where-Object { [string]$_.keys -ieq $keys } | Select-Object -First 1
                if ($binding) {
                    if ($binding.id) {
                        Write-Host "    $keys binding: id=$($binding.id)"
                        if (($keys -eq "ctrl+c" -or $keys -eq "ctrl+space") -and $binding.id -eq "User.claudeCliTranslator.copyKeepSelection") {
                            Write-Host "      warning: this should be repaired by enable-terminal-copy-on-select.ps1"
                        }
                    } elseif ($binding.command) {
                        $bindingJson = $binding.command | ConvertTo-Json -Compress -Depth 10
                        Write-Host "    $keys binding: command=$bindingJson"
                    } else {
                        Write-Host "    $keys binding: present without id/command"
                    }
                } else {
                    Write-Host "    $keys binding: missing"
                }
            }
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
$pythonHotkeys = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like "python*.exe" -and $_.CommandLine -like "*hotkey-double-ctrl.py*"
}
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
