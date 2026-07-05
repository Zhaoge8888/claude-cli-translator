param(
    [ValidateRange(0.20, 0.80)]
    [double]$TranslatorSize = 0.32,

    [switch]$SideBySide
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunTranslator = Join-Path $ScriptDir "run-translator.ps1"

function Resolve-ClaudeCommand {
    $candidates = @()

    if ($env:CLAUDE_TRANSLATOR_CLAUDE_PATH) {
        $candidates += $env:CLAUDE_TRANSLATOR_CLAUDE_PATH
    }

    $roamingNpm = Join-Path $env:APPDATA "npm\claude.cmd"
    if (Test-Path $roamingNpm) {
        $candidates += $roamingNpm
    }

    $npmGlobal = Join-Path $env:USERPROFILE ".npm-global\claude.cmd"
    if (Test-Path $npmGlobal) {
        $candidates += $npmGlobal
    }

    $commands = Get-Command claude -All -ErrorAction SilentlyContinue
    foreach ($command in $commands) {
        if ($command.Source) {
            $candidates += $command.Source
        }
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path $candidate)) {
            continue
        }

        $extension = [System.IO.Path]::GetExtension($candidate)
        if ([string]::IsNullOrWhiteSpace($extension)) {
            continue
        }

        if ($candidate -like "*.cmd") {
            $content = Get-Content -Raw $candidate -ErrorAction SilentlyContinue
            $match = [regex]::Match($content, '"([^"]*claude\.exe)"')
            if ($match.Success) {
                $target = $match.Groups[1].Value
                $candidateDir = Split-Path -Parent $candidate
                $target = $target.Replace("%dp0%", $candidateDir + "\")
                $target = $target.Replace("%~dp0", $candidateDir + "\")
                if (-not (Test-Path $target)) {
                    continue
                }
            }
        }

        return (Resolve-Path $candidate).Path
    }

    return $null
}

$ClaudeCommand = Resolve-ClaudeCommand
if (-not $ClaudeCommand) {
    Write-Host "No working Claude Code launcher found." -ForegroundColor Yellow
    Write-Host "Try reinstalling Claude Code, then rerun this script."
    exit 1
}

if (-not (Get-Command wt.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Windows Terminal wt.exe not found. Install Windows Terminal or open two terminals manually." -ForegroundColor Yellow
    Write-Host "Left pane/window: `"$ClaudeCommand`""
    Write-Host "Right pane/window: powershell -ExecutionPolicy Bypass -File `"$RunTranslator`""
    exit 1
}

$claudeCommand = 'new-tab --title "Claude Code" powershell -NoExit -Command "& ''' + $ClaudeCommand + '''"'
$splitDirection = if ($SideBySide) { "-V" } else { "-H" }
$translatorCommand = 'split-pane ' + $splitDirection + ' --size ' + $TranslatorSize.ToString([System.Globalization.CultureInfo]::InvariantCulture) + ' --title "CLI Translator" powershell -NoExit -ExecutionPolicy Bypass -File "' + $RunTranslator + '"'

Start-Process wt.exe -ArgumentList ($claudeCommand + " ; " + $translatorCommand)
