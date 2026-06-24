param(
    [string]$PythonPath = "python",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 9880,
    [string]$Model = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    [string]$Voice = "Vivian",
    [switch]$Install,
    [switch]$InstallOnly
)

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$PortableVoiceRoot = Join-Path $RepoRoot "voice_runtime"
$PortableServiceRoot = Join-Path $PortableVoiceRoot ".voice-services\qwen3-tts"
$PortableModelCacheRoot = Join-Path $PortableVoiceRoot "model_cache"
$PortableHuggingFaceCache = Join-Path $PortableModelCacheRoot "huggingface"
if (Test-Path -LiteralPath $PortableHuggingFaceCache) {
    $env:HF_HOME = $PortableHuggingFaceCache
    $env:HUGGINGFACE_HUB_CACHE = Join-Path $PortableHuggingFaceCache "hub"
}
if (Test-Path -LiteralPath $PortableServiceRoot) {
    $ServiceRoot = $PortableServiceRoot
}
else {
    $ServiceRoot = Join-Path $RepoRoot ".voice-services\qwen3-tts"
}
$VenvDir = Join-Path $ServiceRoot ".venv"

if ($Install) {
    New-Item -ItemType Directory -Force -Path $ServiceRoot | Out-Null
    & $PythonPath -m venv $VenvDir
    $PythonPath = Join-Path $VenvDir "Scripts\python.exe"
    & $PythonPath -m pip install --upgrade pip
    & $PythonPath -m pip install --upgrade qwen-tts
}
elseif (Test-Path (Join-Path $VenvDir "Scripts\python.exe")) {
    $PythonPath = Join-Path $VenvDir "Scripts\python.exe"
}

if (-not (Get-Command sox -ErrorAction SilentlyContinue)) {
    $SoxCandidate = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "sox.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($SoxCandidate) {
        $env:PATH = "$(Split-Path $SoxCandidate.FullName);$env:PATH"
    }
}

if (-not (Get-Command sox -ErrorAction SilentlyContinue)) {
    Write-Warning "SoX executable was not found on PATH. Qwen3-TTS may fail during audio processing. Install SoX before live synthesis."
}

# Formal local Qwen3-TTS route for E-Moti:
# .\start_qwen3_tts_server.ps1 -Install -Port 9880
if ($InstallOnly) {
    Write-Output "Qwen3-TTS local service environment is ready: $ServiceRoot"
    exit 0
}

$Server = Join-Path $ScriptDir "qwen3_tts_local_server.py"
& $PythonPath $Server --host $HostAddress --port $Port --model $Model --voice $Voice --output-dir (Join-Path $ServiceRoot "output")
