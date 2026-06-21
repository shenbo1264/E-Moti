param(
    [string]$PythonPath = "python",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8899,
    [string]$Device = "cpu",
    [string]$Model = "sensevoice",
    [switch]$Install,
    [switch]$InstallOnly
)

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$ServiceRoot = Join-Path $RepoRoot ".voice-services\sensevoice-asr"
$VenvDir = Join-Path $ServiceRoot ".venv"

if ($Install) {
    New-Item -ItemType Directory -Force -Path $ServiceRoot | Out-Null
    & $PythonPath -m venv $VenvDir
    $PythonPath = Join-Path $VenvDir "Scripts\python.exe"
    & $PythonPath -m pip install --upgrade pip
    & $PythonPath -m pip install --upgrade torch torchaudio funasr modelscope uvicorn fastapi python-multipart
}
elseif (Test-Path (Join-Path $VenvDir "Scripts\python.exe")) {
    $PythonPath = Join-Path $VenvDir "Scripts\python.exe"
}

# Formal local SenseVoice/FunASR OpenAI-compatible ASR route for E-Moti:
# .\start_sensevoice_asr_server.ps1 -Install -Port 8899 -Device cpu -Model sensevoice
if ($InstallOnly) {
    Write-Output "SenseVoice/FunASR local ASR service environment is ready: $ServiceRoot"
    exit 0
}

$ScriptsDir = Split-Path $PythonPath
$FunASRServer = Join-Path $ScriptsDir "funasr-server.exe"
if (-not (Test-Path $FunASRServer)) {
    $FunASRServer = "funasr-server"
}

& $FunASRServer --host $HostAddress --port $Port --device $Device --model $Model
