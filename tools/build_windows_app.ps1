param(
    [switch]$SkipClean,
    [string]$PythonPath = ""
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

function New-PythonInvocation {
    param(
        [string]$Command,
        [string[]]$Arguments = @()
    )

    [pscustomobject]@{
        Command = $Command
        Arguments = $Arguments
    }
}

function Test-PythonInvocation {
    param([pscustomobject]$Invocation)

    try {
        $ProbeArguments = @($Invocation.Arguments) + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")
        & $Invocation.Command @ProbeArguments *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Resolve-PythonInvocation {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        if (-not (Test-Path -LiteralPath $RequestedPath)) {
            throw "Python interpreter not found: $RequestedPath"
        }
        $Requested = New-PythonInvocation -Command $RequestedPath
        if (Test-PythonInvocation -Invocation $Requested) {
            return $Requested
        }
        throw "Python interpreter failed validation: $RequestedPath"
    }

    $Candidates = @()
    if ($env:PYTHON) {
        $Candidates += New-PythonInvocation -Command $env:PYTHON
    }

    $PyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($PyLauncher -and $PyLauncher.Source) {
        $Candidates += New-PythonInvocation -Command $PyLauncher.Source -Arguments @("-3.11")
        $Candidates += New-PythonInvocation -Command $PyLauncher.Source -Arguments @("-3")
    }

    $PythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($PythonCommand -and $PythonCommand.Source) {
        $Candidates += New-PythonInvocation -Command $PythonCommand.Source
    }

    if ($env:LOCALAPPDATA) {
        foreach ($Version in @("Python311", "Python312", "Python313")) {
            $Candidates += New-PythonInvocation -Command (Join-Path $env:LOCALAPPDATA "Programs\Python\$Version\python.exe")
        }
    }

    foreach ($Candidate in $Candidates) {
        if ((Test-Path -LiteralPath $Candidate.Command) -and (Test-PythonInvocation -Invocation $Candidate)) {
            return $Candidate
        }
    }

    throw "No working Python 3.11+ interpreter found. Pass -PythonPath to tools\build_windows_app.ps1."
}

if (-not (Test-Path -LiteralPath $EntryPath)) {
    throw "Missing PyInstaller entrypoint: $EntryPath"
}
if (-not (Test-Path -LiteralPath $AssetsPath)) {
    throw "Missing assets directory: $AssetsPath"
}

$ResolvedPython = Resolve-PythonInvocation -RequestedPath $PythonPath
Write-Host "Using Python: $($ResolvedPython.Command) $($ResolvedPython.Arguments -join ' ')"

if (-not $SkipClean) {
    Remove-Item -LiteralPath $AppDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeCharacterDir | Out-Null

# Keep the frozen pack equivalent to the validated source character pack.
# Required examples: item_icons, portrait_manifest.json, portraits, preview, portrait_assets_provenance.md, LICENSE.md.
Get-ChildItem -Force -LiteralPath $SourceCharacterDir | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $RuntimeCharacterDir -Recurse -Force
}

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
    $PythonArguments = @($ResolvedPython.Arguments) + $Arguments
    & $ResolvedPython.Command @PythonArguments
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
