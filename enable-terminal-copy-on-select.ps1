param(
    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"

function Get-TerminalSettingsPaths {
    @(
        (Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"),
        (Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe\LocalState\settings.json"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\Windows Terminal\settings.json")
    ) | Where-Object { Test-Path $_ }
}

$paths = @(Get-TerminalSettingsPaths)
if ($paths.Count -eq 0) {
    Write-Host "Windows Terminal settings.json not found. Skipping copyOnSelect setup."
    exit 0
}

foreach ($path in $paths) {
    $raw = Get-Content -Raw -Encoding UTF8 $path
    $settings = $raw | ConvertFrom-Json

    $changed = $false

    if ($settings.PSObject.Properties.Name -contains "copyOnSelect") {
        if ($settings.copyOnSelect -ne $true) {
            $settings.copyOnSelect = $true
            $changed = $true
        }
    } else {
        $settings | Add-Member -NotePropertyName "copyOnSelect" -NotePropertyValue $true
        $changed = $true
    }

    if ($settings.PSObject.Properties.Name -contains "copyFormatting") {
        if ($settings.copyFormatting -ne "none") {
            $settings.copyFormatting = "none"
            $changed = $true
        }
    } else {
        $settings | Add-Member -NotePropertyName "copyFormatting" -NotePropertyValue "none"
        $changed = $true
    }

    if (-not $changed) {
        Write-Host "Windows Terminal copyOnSelect already enabled: $path"
        continue
    }

    $backup = "$path.claude-cli-translator.$(Get-Date -Format yyyyMMddHHmmss).bak"
    Write-Host "Updating Windows Terminal settings: $path"
    Write-Host "Backup: $backup"

    if (-not $WhatIfOnly) {
        Copy-Item -LiteralPath $path -Destination $backup -Force
        $settings | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $path -Encoding UTF8
    }
}

