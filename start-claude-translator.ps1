param(
    [ValidateRange(0.20, 0.80)]
    [double]$TranslatorSize = 0.32,

    [switch]$SideBySide
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartHotkey = Join-Path $ScriptDir "start-hotkey.ps1"
$LaunchSplit = Join-Path $ScriptDir "launch-split.ps1"

Set-Location $ScriptDir

powershell -ExecutionPolicy Bypass -File $StartHotkey

$argsForLaunch = @("-ExecutionPolicy", "Bypass", "-File", $LaunchSplit, "-TranslatorSize", $TranslatorSize)
if ($SideBySide) {
    $argsForLaunch += "-SideBySide"
}

powershell @argsForLaunch
