param(
    [ValidateRange(0.20, 0.80)]
    [double]$TranslatorSize = 0.32,

    [switch]$SideBySide,

    [switch]$SkipTerminalCopyOnSelect
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartHotkey = Join-Path $ScriptDir "start-hotkey.ps1"
$LaunchSplit = Join-Path $ScriptDir "launch-split.ps1"
$EnableCopyOnSelect = Join-Path $ScriptDir "enable-terminal-copy-on-select.ps1"

Set-Location $ScriptDir

if (-not $SkipTerminalCopyOnSelect -and (Test-Path $EnableCopyOnSelect)) {
    powershell -NoProfile -ExecutionPolicy Bypass -File $EnableCopyOnSelect
}

powershell -ExecutionPolicy Bypass -File $StartHotkey

$argsForLaunch = @("-ExecutionPolicy", "Bypass", "-File", $LaunchSplit, "-TranslatorSize", $TranslatorSize)
if ($SideBySide) {
    $argsForLaunch += "-SideBySide"
}

powershell @argsForLaunch
