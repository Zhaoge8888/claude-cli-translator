$ErrorActionPreference = "Stop"

$requestDir = Join-Path $env:LOCALAPPDATA "ClaudeCliTranslator\requests"
New-Item -ItemType Directory -Force -Path $requestDir | Out-Null

$savedClipboard = Get-Clipboard -Raw -ErrorAction SilentlyContinue
Set-Clipboard -Value ""

$wshell = New-Object -ComObject WScript.Shell
$wshell.SendKeys("^+c")
Start-Sleep -Milliseconds 500

$text = Get-Clipboard -Raw -ErrorAction SilentlyContinue
if ($null -ne $savedClipboard) {
    Set-Clipboard -Value $savedClipboard
}

if ([string]::IsNullOrWhiteSpace($text)) {
    Write-Host "No selected text was copied." -ForegroundColor Yellow
    exit 1
}

$fileName = "request_{0}_{1}.txt" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), (Get-Random -Minimum 1000 -Maximum 9999)
$path = Join-Path $requestDir $fileName
[System.IO.File]::WriteAllText($path, $text, [System.Text.Encoding]::UTF8)
Write-Host "Sent to translator pane: $path"
