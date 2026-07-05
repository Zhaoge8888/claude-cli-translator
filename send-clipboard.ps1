$ErrorActionPreference = "Stop"

$requestDir = Join-Path $env:LOCALAPPDATA "ClaudeCliTranslator\requests"
New-Item -ItemType Directory -Force -Path $requestDir | Out-Null

$text = Get-Clipboard -Raw -ErrorAction SilentlyContinue
if ([string]::IsNullOrWhiteSpace($text)) {
    Write-Host "Clipboard is empty." -ForegroundColor Yellow
    exit 1
}

$fileName = "request_{0}_{1}.txt" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), (Get-Random -Minimum 1000 -Maximum 9999)
$path = Join-Path $requestDir $fileName
[System.IO.File]::WriteAllText($path, $text, [System.Text.Encoding]::UTF8)
Write-Host "Sent clipboard to translator pane: $path"

