[CmdletBinding()]
param(
    [switch]$PlanOnly,
    [switch]$SkipDemo
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0
$Root = $PSScriptRoot

if (-not [Environment]::Is64BitOperatingSystem) {
    throw "Talking-Head Ad Machine requires 64-bit Windows 11."
}
$WindowsBuild = [Environment]::OSVersion.Version.Build
if ($WindowsBuild -lt 22000) {
    throw "Talking-Head Ad Machine requires Windows 11 (build 22000 or newer)."
}

Write-Host "Talking-Head Ad Machine installation plan:"
Write-Host "  1. Install uv, FFmpeg, and current Node LTS through Winget when missing."
Write-Host "  2. Download the pinned Windows x64 whisper.cpp release into this folder."
Write-Host "  3. Create an isolated Python environment in this folder."
Write-Host "  4. Install pinned Kinocut, MCP, HyperFrames, and its browser."
Write-Host "  5. Run doctor and render the included demo."
if ($PlanOnly) { exit 0 }

if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
    throw "Winget is required. Update or install Microsoft App Installer, then ask the agent to rerun install.ps1."
}

function Refresh-Path {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $runtimePath = Join-Path $Root ".runtime\whisper.cpp\Release"
    $env:Path = "$runtimePath;$machinePath;$userPath"
}

function Ensure-WingetPackage {
    param([string]$Command, [string]$Id)
    if (Get-Command $Command -ErrorAction SilentlyContinue) { return }
    & winget.exe install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Winget could not install $Id (exit $LASTEXITCODE)."
    }
    Refresh-Path
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "$Id installed, but $Command is not available in PATH. Restart Codex or Claude Code and rerun install.ps1."
    }
}

function Ensure-CompatibleNode {
    $compatible = $false
    $node = Get-Command "node.exe" -ErrorAction SilentlyContinue
    if ($node) {
        $versionText = (& node.exe --version).TrimStart([char]"v")
        $major = 0
        if ([int]::TryParse(($versionText -split "\.")[0], [ref]$major)) {
            $compatible = $major -ge 22
        }
    }
    if ($compatible) { return }
    & winget.exe upgrade --id "OpenJS.NodeJS.LTS" --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        & winget.exe install --id "OpenJS.NodeJS.LTS" --exact --silent --accept-package-agreements --accept-source-agreements
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Winget could not install a compatible Node LTS release (exit $LASTEXITCODE)."
    }
    Refresh-Path
}

Ensure-WingetPackage -Command "uv.exe" -Id "astral-sh.uv"
Ensure-WingetPackage -Command "ffmpeg.exe" -Id "Gyan.FFmpeg"
Ensure-CompatibleNode
Refresh-Path

$WhisperRoot = Join-Path $Root ".runtime\whisper.cpp"
$WhisperExe = Join-Path $WhisperRoot "Release\whisper-cli.exe"
if (-not (Test-Path $WhisperExe)) {
    $Archive = Join-Path ([IO.Path]::GetTempPath()) "talking-head-whisper-1.9.1-x64.zip"
    $Url = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/whisper-bin-x64.zip"
    Invoke-WebRequest -Uri $Url -OutFile $Archive -UseBasicParsing
    $ActualHash = (Get-FileHash -Path $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $ExpectedHash = "7d8be46ecd31828e1eb7a2ecdd0d6b314feafd82163038ab6092594b0a063539"
    if ($ActualHash -ne $ExpectedHash) {
        Remove-Item -Force $Archive
        throw "The downloaded whisper.cpp archive failed its checksum."
    }
    if (Test-Path $WhisperRoot) { Remove-Item -Recurse -Force $WhisperRoot }
    New-Item -ItemType Directory -Force -Path $WhisperRoot | Out-Null
    Expand-Archive -Path $Archive -DestinationPath $WhisperRoot -Force
    Remove-Item -Force $Archive
}
Refresh-Path

$ExistingPython = Join-Path $Root ".venv\Scripts\python.exe"
$ClearEnvironment = $false
if (Test-Path $ExistingPython) {
    & $ExistingPython -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    $ClearEnvironment = $LASTEXITCODE -ne 0
}
if ($ClearEnvironment) {
    & uv.exe venv --clear --python 3.12 (Join-Path $Root ".venv")
} else {
    & uv.exe venv --allow-existing --python 3.12 (Join-Path $Root ".venv")
}
if ($LASTEXITCODE -ne 0) { throw "uv could not create the Python environment." }

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root;$($env:PYTHONPATH)" } else { $Root }
& $Python -m ad_machine.cli setup --apply --json
if ($LASTEXITCODE -ne 0) { throw "Product setup failed." }
& $Python -m ad_machine.cli doctor --json
if ($LASTEXITCODE -ne 0) { throw "The compatibility check failed." }
if (-not $SkipDemo) {
    & $Python -m ad_machine.cli demo --json
    if ($LASTEXITCODE -ne 0) { throw "The included demo did not render successfully." }
}

Write-Host "Talking-Head Ad Machine installation completed successfully."
