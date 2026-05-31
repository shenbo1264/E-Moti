param(
    [switch]$SkipAppBuild,
    [string]$ISCCPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AppBuildScript = Join-Path $RepoRoot "tools\build_windows_app.ps1"
$InstallerScript = Join-Path $RepoRoot "packaging\e-moti-installer.iss"
$InstallerPath = Join-Path $RepoRoot "dist\installer\E-Moti_Setup_0.1.0.exe"

function Resolve-ISCCPath {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        if (Test-Path -LiteralPath $RequestedPath) {
            return $RequestedPath
        }
        throw "Inno Setup compiler not found: $RequestedPath"
    }

    $Command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($Command -and $Command.Source) {
        return $Command.Source
    }

    $Candidates = @()
    if ($env:ProgramFiles) {
        $Candidates += Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"
    }
    if (${env:ProgramFiles(x86)}) {
        $Candidates += Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    }
    if ($env:LOCALAPPDATA) {
        $Candidates += Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
    }

    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate) {
            return $Candidate
        }
    }

    throw "Inno Setup compiler not found. Add ISCC.exe to PATH or pass -ISCCPath."
}
if (-not (Test-Path -LiteralPath $InstallerScript)) {
    throw "Missing Inno Setup script: $InstallerScript"
}

$ResolvedISCCPath = Resolve-ISCCPath -RequestedPath $ISCCPath

if (-not $SkipAppBuild) {
    & $AppBuildScript
    if ($LASTEXITCODE -ne 0) {
        throw "App build script failed with exit code $LASTEXITCODE"
    }
}

Push-Location (Join-Path $RepoRoot "packaging")
try {
    & $ResolvedISCCPath $InstallerScript
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
