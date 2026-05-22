param(
    [switch]$SkipAppBuild,
    [string]$ISCCPath = "C:\Users\19970\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AppBuildScript = Join-Path $RepoRoot "tools\build_windows_app.ps1"
$InstallerScript = Join-Path $RepoRoot "packaging\e-moti-installer.iss"
$InstallerPath = Join-Path $RepoRoot "dist\installer\E-Moti_Setup_0.1.0.exe"

if (-not (Test-Path -LiteralPath $ISCCPath)) {
    throw "Inno Setup compiler not found: $ISCCPath"
}
if (-not (Test-Path -LiteralPath $InstallerScript)) {
    throw "Missing Inno Setup script: $InstallerScript"
}

if (-not $SkipAppBuild) {
    & $AppBuildScript
    if ($LASTEXITCODE -ne 0) {
        throw "App build script failed with exit code $LASTEXITCODE"
    }
}

Push-Location (Join-Path $RepoRoot "packaging")
try {
    & $ISCCPath $InstallerScript
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compiler failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $InstallerPath)) {
    throw "Inno Setup did not create expected installer: dist\installer\E-Moti_Setup_0.1.0.exe"
}

Write-Host "Built dist\installer\E-Moti_Setup_0.1.0.exe"
