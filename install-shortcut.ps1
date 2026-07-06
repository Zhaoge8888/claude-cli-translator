param(
    [ValidateRange(0.20, 0.80)]
    [double]$TranslatorSize = 0.32,

    [switch]$SideBySide,

    [switch]$NoTaskbarPin
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartScript = Join-Path $ScriptDir "start-claude-translator.ps1"
$LauncherCmd = Join-Path $ScriptDir "launcher.cmd"

if (-not (Test-Path $StartScript)) {
    throw "Missing start script: $StartScript"
}

if (-not (Test-Path $LauncherCmd)) {
    throw "Missing launcher: $LauncherCmd"
}

function Get-PowerShellPath {
    $path = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
    if (Test-Path $path) {
        return $path
    }
    return "powershell.exe"
}

function Get-ShortcutIcon {
    $appIcon = Join-Path $ScriptDir "assets\app-icon.ico"
    if (Test-Path $appIcon) {
        return $appIcon
    }

    $wt = Get-Command wt.exe -ErrorAction SilentlyContinue
    if ($wt -and $wt.Source) {
        return "$($wt.Source),0"
    }

    $powershell = Get-PowerShellPath
    return "$powershell,0"
}

function New-LauncherShortcut {
    param(
        [string]$ShortcutPath,
        [string]$Arguments
    )

    $parent = Split-Path -Parent $ShortcutPath
    New-Item -ItemType Directory -Force -Path $parent | Out-Null

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = Get-PowerShellPath
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $ScriptDir
    $shortcut.IconLocation = Get-ShortcutIcon
    $shortcut.Description = "Launch Claude Code with the side-pane translator"
    $shortcut.Save()
}

function Try-PinShortcutToTaskbar {
    param([string]$ShortcutPath)

    try {
        $shell = New-Object -ComObject Shell.Application
        $folderPath = Split-Path -Parent $ShortcutPath
        $fileName = Split-Path -Leaf $ShortcutPath
        $folder = $shell.Namespace($folderPath)
        if (-not $folder) {
            return $false
        }

        $item = $folder.ParseName($fileName)
        if (-not $item) {
            return $false
        }

        foreach ($verb in $item.Verbs()) {
            $name = $verb.Name.Replace("&", "")
            if ($name -match "taskbar|Pin to Tas|Unpin from Tas") {
                if ($name -match "Unpin") {
                    return $true
                }
                $verb.DoIt()
                Start-Sleep -Milliseconds 500
                return $true
            }
        }
    } catch {
        return $false
    }

    return $false
}

$scriptArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$StartScript`"", "-TranslatorSize", $TranslatorSize.ToString([System.Globalization.CultureInfo]::InvariantCulture))
if ($SideBySide) {
    $scriptArgs += "-SideBySide"
}
$shortcutArguments = $scriptArgs -join " "

$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
$startMenuDir = Join-Path $programs "Claude Code Translator"

$desktopShortcut = Join-Path $desktop "Claude Code Translator.lnk"
$startMenuShortcut = Join-Path $startMenuDir "Claude Code Translator.lnk"

New-LauncherShortcut -ShortcutPath $desktopShortcut -Arguments $shortcutArguments
New-LauncherShortcut -ShortcutPath $startMenuShortcut -Arguments $shortcutArguments

Write-Host "Created desktop shortcut: $desktopShortcut"
Write-Host "Created Start Menu shortcut: $startMenuShortcut"

if ($NoTaskbarPin) {
    Write-Host "Skipped taskbar pin attempt."
    exit 0
}

$pinned = Try-PinShortcutToTaskbar -ShortcutPath $startMenuShortcut
if ($pinned) {
    Write-Host "Taskbar pin attempt completed."
} else {
    Write-Host "Windows did not expose a taskbar pin verb for automation."
    Write-Host "Manual pin: Start menu -> search 'Claude Code Translator' -> right click -> Pin to taskbar."
}
