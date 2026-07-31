[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "The product is not installed. Ask Codex or Claude Code to run install.ps1."
}
$runtimePath = Join-Path $Root ".runtime\whisper.cpp\Release"
$env:Path = "$runtimePath;$(Join-Path $Root '.venv\Scripts');$(Join-Path $Root 'node_modules\.bin');$($env:Path)"
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root;$($env:PYTHONPATH)" } else { $Root }
& $Python -m ad_machine.cli @Arguments
exit $LASTEXITCODE
