$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Test-Path ".\config.json")) {
    Copy-Item ".\config.example.json" ".\config.json"
}

function Test-PythonCommand {
    param([string]$Command)

    if ([string]::IsNullOrWhiteSpace($Command)) {
        return $false
    }

    try {
        $process = Start-Process -FilePath $Command -ArgumentList "--version" -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$env:TEMP\cli-translator-python.out" -RedirectStandardError "$env:TEMP\cli-translator-python.err"
        return $process.ExitCode -eq 0
    } catch {
        return $false
    }
}

$candidates = @()
if ($env:CLI_TRANSLATOR_PYTHON) {
    $candidates += $env:CLI_TRANSLATOR_PYTHON
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand -and $pythonCommand.Source -notlike "*\WindowsApps\python.exe") {
    $candidates += $pythonCommand.Source
}

$codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path $codexPython) {
    $candidates += $codexPython
}

$Python = $null
foreach ($candidate in $candidates) {
    if (Test-PythonCommand $candidate) {
        $Python = $candidate
        break
    }
}

if (-not $Python) {
    Write-Host "Python not found. Install Python 3.9+ or set CLI_TRANSLATOR_PYTHON to python.exe." -ForegroundColor Yellow
    exit 1
}

& $Python ".\translator-pane.py" @args
