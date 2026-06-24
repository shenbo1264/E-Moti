from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_voice_service_deployment_scripts_exist_without_private_paths() -> None:
    scripts = [
        REPO_ROOT / "tools" / "voice_services" / "start_qwen3_tts_server.ps1",
        REPO_ROOT / "tools" / "voice_services" / "start_sensevoice_asr_server.ps1",
    ]

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "D:" + "\\" not in text
        assert "\u5b66\u5de5\u6587\u6863" not in text
        assert "$PSScriptRoot" in text


def test_qwen3_tts_deployment_script_uses_local_http_contract() -> None:
    script = (REPO_ROOT / "tools" / "voice_services" / "start_qwen3_tts_server.ps1").read_text(
        encoding="utf-8"
    )

    assert "qwen3_tts_local_server.py" in script
    assert "-Port 9880" in script
    assert "InstallOnly" in script
    assert "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice" in script
    assert "Qwen/Qwen3-TTS-0.6B" not in script
    assert "Vivian" in script
    assert "sox" in script.lower()


def test_sensevoice_asr_deployment_script_uses_formal_local_route() -> None:
    script = (REPO_ROOT / "tools" / "voice_services" / "start_sensevoice_asr_server.ps1").read_text(
        encoding="utf-8"
    )

    assert "funasr" in script.lower()
    assert "funasr-server" in script
    assert "funasr.server.openai_api_server" not in script
    assert "sensevoice" in script
    assert "-Port 8899" in script
    assert "Device" in script
    assert "[string]$ServiceRoot" in script
    assert "EMOTI_SENSEVOICE_SERVICE_ROOT" in script
    assert "$env:LOCALAPPDATA" in script
    assert "--device" in script
    assert "InstallOnly" in script
    assert "[string]::IsNullOrWhiteSpace($ScriptsDir)" in script
    assert "Invoke-CheckedCommand" in script
    assert "$LASTEXITCODE" in script
    assert "torch==2.11.0" in script
    assert "torchaudio==2.11.0" in script
    assert "https://download.pytorch.org/whl/cpu" in script
