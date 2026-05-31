param(
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $RepoRoot "dist"
$AppDir = Join-Path $DistDir "E-Moti"
$BuildDir = Join-Path $RepoRoot "build\pyinstaller"
$RuntimeAssetsRoot = Join-Path $BuildDir "runtime_assets\assets"
$RuntimeCharacterDir = Join-Path $RuntimeAssetsRoot "companion\original_oc"
$EntryPath = Join-Path $RepoRoot "packaging\launch_control_panel.py"
$AssetsPath = Join-Path $RepoRoot "assets"
$SourceCharacterDir = Join-Path $AssetsPath "companion\original_oc"
$SrcPath = Join-Path $RepoRoot "src"
$ExePath = Join-Path $AppDir "E-Moti.exe"

if (-not (Test-Path -LiteralPath $EntryPath)) {
    throw "Missing PyInstaller entrypoint: $EntryPath"
}
if (-not (Test-Path -LiteralPath $AssetsPath)) {
    throw "Missing assets directory: $AssetsPath"
}

if (-not $SkipClean) {
    Remove-Item -LiteralPath $AppDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeCharacterDir | Out-Null

foreach ($FileName in @("character.json", "motion_manifest.json", "spritesheet.png", "shop_items.json", "dialogue_style.json")) {
    $SourceFile = Join-Path $SourceCharacterDir $FileName
    if (Test-Path -LiteralPath $SourceFile) {
        Copy-Item -LiteralPath $SourceFile -Destination $RuntimeCharacterDir -Force
    }
}
Copy-Item -LiteralPath (Join-Path $SourceCharacterDir "item_icons") -Destination $RuntimeCharacterDir -Recurse -Force

$AddData = "$RuntimeAssetsRoot;assets"
$Arguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--windowed",
    "--name", "E-Moti",
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    "--specpath", $BuildDir,
    "--paths", $SrcPath,
    "--add-data", $AddData,
    "packaging\launch_control_panel.py"
)

Push-Location $RepoRoot
try {
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "PyInstaller did not create expected app executable: dist\E-Moti\E-Moti.exe"
}

Write-Host "Built dist\E-Moti\E-Moti.exe"
