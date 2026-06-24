param(
    [string]$PythonPath = "python",
    [string]$ServiceRoot = "",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8899,
    [string]$Device = "cpu",
    [string]$Model = "sensevoice",
    [switch]$Install,
    [switch]$InstallOnly
)

$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [scriptblock]$Command,
        [string]$FailureMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code $LASTEXITCODE)"
    }
}

$ScriptDir = $PSScriptRoot
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$PortableVoiceRoot = Join-Path $RepoRoot "voice_runtime"
$PortableServiceRoot = Join-Path $PortableVoiceRoot ".voice-services\sensevoice-asr"
if ([string]::IsNullOrWhiteSpace($ServiceRoot)) {
    if ($env:EMOTI_SENSEVOICE_SERVICE_ROOT) {
        $ServiceRoot = $env:EMOTI_SENSEVOICE_SERVICE_ROOT
    }
    elseif (Test-Path -LiteralPath $PortableServiceRoot) {
        $ServiceRoot = $PortableServiceRoot
    }
    elseif ($env:LOCALAPPDATA) {
        $ServiceRoot = Join-Path $env:LOCALAPPDATA "E-Moti\voice-services\sensevoice-asr"
    }
    else {
        $ServiceRoot = Join-Path $RepoRoot ".voice-services\sensevoice-asr"
    }
}
$VenvDir = Join-Path $ServiceRoot ".venv"

if ($Install) {
    New-Item -ItemType Directory -Force -Path $ServiceRoot | Out-Null
    Invoke-CheckedCommand { & $PythonPath -m venv $VenvDir } "Failed to create SenseVoice/FunASR virtual environment"
    $PythonPath = Join-Path $VenvDir "Scripts\python.exe"
    Invoke-CheckedCommand { & $PythonPath -m pip install --upgrade pip } "Failed to upgrade pip in SenseVoice/FunASR environment"
    Invoke-CheckedCommand { & $PythonPath -m pip install --upgrade "torch==2.11.0" "torchaudio==2.11.0" --index-url "https://download.pytorch.org/whl/cpu" } "Failed to install PyTorch CPU dependencies"
    Invoke-CheckedCommand { & $PythonPath -m pip install --upgrade funasr modelscope uvicorn fastapi python-multipart } "Failed to install SenseVoice/FunASR dependencies"
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
$FunASRServer = "funasr-server"
if (-not [string]::IsNullOrWhiteSpace($ScriptsDir)) {
    $CandidateFunASRServer = Join-Path $ScriptsDir "funasr-server.exe"
    if (Test-Path $CandidateFunASRServer) {
        $FunASRServer = $CandidateFunASRServer
    }
}

if ($FunASRServer -eq "funasr-server" -and -not (Get-Command $FunASRServer -ErrorAction SilentlyContinue)) {
    throw "funasr-server was not found. Run start_sensevoice_asr_server.ps1 -Install -InstallOnly first."
}

Invoke-CheckedCommand { & $FunASRServer --host $HostAddress --port $Port --device $Device --model $Model } "funasr-server exited with an error"
