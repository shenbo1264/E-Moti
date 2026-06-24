param(
    [string]$GPTSoVITSRoot = "",
    [string]$PythonPath = "",
    [string]$GPTWeight = $(if ($env:EMOTI_IKAROS_GPT_WEIGHT) { $env:EMOTI_IKAROS_GPT_WEIGHT } else { "" }),
    [string]$SoVITSWeight = $(if ($env:EMOTI_IKAROS_SOVITS_WEIGHT) { $env:EMOTI_IKAROS_SOVITS_WEIGHT } else { "" }),
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 9882,
    [switch]$HalfPrecision,
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$PortableVoiceRoot = Join-Path $RepoRoot "voice_runtime"
$PortableGPTSoVITSRoot = Join-Path $PortableVoiceRoot "GPT-SoVITS"
$PortableGPTSoVITSPython = Join-Path $PortableVoiceRoot "gptsovits-venv\Scripts\python.exe"

if (-not $GPTSoVITSRoot) {
    if ($env:EMOTI_GPTSOVITS_ROOT) {
        $GPTSoVITSRoot = $env:EMOTI_GPTSOVITS_ROOT
    }
    elseif (Test-Path -LiteralPath $PortableGPTSoVITSRoot) {
        $GPTSoVITSRoot = $PortableGPTSoVITSRoot
    }
    else {
        $GPTSoVITSRoot = "E:\E_Moti_voice\GPT-SoVITS"
    }
}

if (-not $PythonPath) {
    if ($env:EMOTI_GPTSOVITS_PYTHON) {
        $PythonPath = $env:EMOTI_GPTSOVITS_PYTHON
    }
    elseif (Test-Path -LiteralPath $PortableGPTSoVITSPython) {
        $PythonPath = $PortableGPTSoVITSPython
    }
    else {
        $PythonPath = "E:\E_Moti_voice\gptsovits-venv\Scripts\python.exe"
    }
}

if (-not $GPTWeight) {
    $GPTWeight = Join-Path $GPTSoVITSRoot "GPT_weights_v2\ikaros_curated160_v2-e4.ckpt"
}
if (-not $SoVITSWeight) {
    $SoVITSWeight = Join-Path $GPTSoVITSRoot "SoVITS_weights_v2\ikaros_full642_v2_e3_s1926.pth"
}

if (-not (Test-Path -LiteralPath $GPTSoVITSRoot)) {
    throw "GPT-SoVITS root not found: $GPTSoVITSRoot"
}
if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "GPT-SoVITS Python not found: $PythonPath"
}
if (-not (Test-Path -LiteralPath $GPTWeight)) {
    throw "Ikaros GPT weight not found: $GPTWeight"
}
if (-not (Test-Path -LiteralPath $SoVITSWeight)) {
    throw "Ikaros SoVITS weight not found: $SoVITSWeight"
}

$env:PYTHONPATH = "$GPTSoVITSRoot;$GPTSoVITSRoot\GPT_SoVITS"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$apiScript = Join-Path $GPTSoVITSRoot "api.py"
$logPath = Join-Path $GPTSoVITSRoot "ikaros_curated160_api_9882.log"
$precisionFlag = if ($HalfPrecision) { "-hp" } else { "-fp" }
$arguments = @(
    "-s",
    $apiScript,
    "-s",
    $SoVITSWeight,
    "-g",
    $GPTWeight,
    "-d",
    "cuda",
    "-a",
    $HostAddress,
    "-p",
    [string]$Port,
    $precisionFlag
)

Write-Host "Starting Ikaros GPT-SoVITS on http://$HostAddress`:$Port"
Write-Host "GPT weight: $GPTWeight"
Write-Host "SoVITS weight: $SoVITSWeight"
Write-Host "Log: $logPath"

if ($NoWait) {
    $command = "Set-Location '$GPTSoVITSRoot'; `$env:PYTHONPATH='$env:PYTHONPATH'; `$env:PYTHONUTF8='1'; `$env:PYTHONIOENCODING='utf-8'; & '$PythonPath' $($arguments | ForEach-Object { if ($_ -match '\s') { """" + $_ + """" } else { $_ } }) *> '$logPath'"
    Start-Process -FilePath powershell -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command) -WindowStyle Hidden
    return
}

Set-Location -LiteralPath $GPTSoVITSRoot
& $PythonPath @arguments 2>&1 | Tee-Object -FilePath $logPath
