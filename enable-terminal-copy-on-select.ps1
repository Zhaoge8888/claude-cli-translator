param(
    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"

$TranslatorCopyActionId = "User.claudeCliTranslator.copyKeepSelection"
$TranslatorCopyCommand = [ordered]@{
    action = "copy"
    singleLine = $false
    dismissSelection = $false
}

function Get-TerminalSettingsPaths {
    @(
        (Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"),
        (Join-Path $env:LOCALAPPDATA "Packages\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe\LocalState\settings.json"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\Windows Terminal\settings.json")
    ) | Where-Object { Test-Path $_ }
}

function ConvertTo-Array {
    param($Value)

    if ($null -eq $Value) {
        return @()
    }

    if ($Value -is [array]) {
        return @($Value)
    }

    return @($Value)
}

function Ensure-JsonArrayProperty {
    param(
        [pscustomobject]$Object,
        [string]$Name
    )

    if (-not ($Object.PSObject.Properties.Name -contains $Name)) {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue @()
    } elseif ($null -eq $Object.$Name) {
        $Object.$Name = @()
    }
}

function Ensure-CopyAction {
    param([pscustomobject]$Settings)

    Ensure-JsonArrayProperty -Object $Settings -Name "actions"
    $actions = @(ConvertTo-Array $Settings.actions)
    $existing = $actions | Where-Object { $_.id -eq $TranslatorCopyActionId } | Select-Object -First 1

    $command = [pscustomobject]$TranslatorCopyCommand
    if ($existing) {
        $currentJson = $existing.command | ConvertTo-Json -Compress -Depth 10
        $desiredJson = $command | ConvertTo-Json -Compress -Depth 10
        $existing.command = $command
        return $currentJson -ne $desiredJson
    }

    $Settings.actions = @(
        [pscustomobject]@{
            command = $command
            id = $TranslatorCopyActionId
        }
    ) + $actions
    return $true
}

function Ensure-Keybinding {
    param(
        [pscustomobject]$Settings,
        [string]$Keys
    )

    Ensure-JsonArrayProperty -Object $Settings -Name "keybindings"
    $keybindings = @(ConvertTo-Array $Settings.keybindings)
    $matched = $false
    $changed = $false

    foreach ($binding in $keybindings) {
        if ([string]$binding.keys -ieq $Keys) {
            $matched = $true
            if ($binding.PSObject.Properties.Name -contains "command") {
                $binding.PSObject.Properties.Remove("command")
                $changed = $true
            }
            if ($binding.PSObject.Properties.Name -contains "id") {
                if ($binding.id -ne $TranslatorCopyActionId) {
                    $binding.id = $TranslatorCopyActionId
                    $changed = $true
                }
            } else {
                $binding | Add-Member -NotePropertyName "id" -NotePropertyValue $TranslatorCopyActionId
                $changed = $true
            }
        }
    }

    if (-not $matched) {
        $Settings.keybindings = @(
            [pscustomobject]@{
                id = $TranslatorCopyActionId
                keys = $Keys
            }
        ) + $keybindings
        return $true
    }

    return $changed
}

function Get-DefaultCopyActionId {
    param([pscustomobject]$Settings)

    $actions = @(ConvertTo-Array $Settings.actions)
    $copyAction = $actions | Where-Object {
        $_.id -ne $TranslatorCopyActionId -and $_.command -and $_.command.action -eq "copy"
    } | Select-Object -First 1

    if ($copyAction -and $copyAction.id) {
        return [string]$copyAction.id
    }

    return $null
}

function Restore-Or-Remove-ManagedKeybinding {
    param(
        [pscustomobject]$Settings,
        [string]$Keys,
        [string]$RestoreId
    )

    Ensure-JsonArrayProperty -Object $Settings -Name "keybindings"
    $keybindings = @(ConvertTo-Array $Settings.keybindings)
    $changed = $false
    $kept = @()

    foreach ($binding in $keybindings) {
        if ([string]$binding.keys -ieq $Keys -and $binding.id -eq $TranslatorCopyActionId) {
            if ($RestoreId) {
                $binding.id = $RestoreId
                $kept += $binding
            }
            $changed = $true
        } else {
            $kept += $binding
        }
    }

    if ($changed) {
        $Settings.keybindings = $kept
    }

    return $changed
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

    if (Ensure-CopyAction -Settings $settings) {
        $changed = $true
    }

    if (Ensure-Keybinding -Settings $settings -Keys "ctrl+shift+c") {
        $changed = $true
    }

    $defaultCopyActionId = Get-DefaultCopyActionId -Settings $settings
    if (Restore-Or-Remove-ManagedKeybinding -Settings $settings -Keys "ctrl+c" -RestoreId $defaultCopyActionId) {
        $changed = $true
    }
    if (Restore-Or-Remove-ManagedKeybinding -Settings $settings -Keys "ctrl+space" -RestoreId $null) {
        $changed = $true
    }

    if (-not $changed) {
        Write-Host "Windows Terminal copy settings already enabled: $path"
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
