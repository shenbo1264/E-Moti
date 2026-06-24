from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_voice_service_preflight_reports_endpoint_status(tmp_path, monkeypatch) -> None:
    from tools.voice_services import preflight_voice_services

    calls: list[str] = []

    def fake_probe(url: str, timeout: float) -> tuple[bool, str]:
        calls.append(url)
        return (True, "listening")

    monkeypatch.setattr(preflight_voice_services, "_probe_http", fake_probe)
    report = tmp_path / "preflight.json"

    code = preflight_voice_services.main(["--report", str(report)])

    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["qwen3tts"]["ok"] is True
    assert payload["qwen3tts"]["label"] == "Qwen3TTS"
    assert payload["gptsovits"]["ok"] is True
    assert payload["gptsovits"]["label"] == "GPT-SoVITS"
    assert payload["sensevoice_asr"]["ok"] is True
    assert payload["sensevoice_asr"]["label"] == "SenseVoice ASR"
    assert calls == [
        "http://127.0.0.1:9880/tts",
        "http://127.0.0.1:9882/",
        "http://127.0.0.1:8899/v1/models",
    ]


def test_voice_service_preflight_exits_nonzero_when_any_service_is_down(tmp_path, monkeypatch) -> None:
    from tools.voice_services import preflight_voice_services

    def fake_probe(url: str, timeout: float) -> tuple[bool, str]:
        if "9882" in url:
            return (False, "connection refused")
        return (True, "listening")

    monkeypatch.setattr(preflight_voice_services, "_probe_http", fake_probe)
    report = tmp_path / "preflight.json"

    code = preflight_voice_services.main(["--report", str(report), "--timeout", "0.5"])

    assert code == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["gptsovits"]["ok"] is False
    assert payload["gptsovits"]["message"] == "connection refused"


def test_voice_service_preflight_script_can_run_as_file() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "tools" / "voice_services" / "preflight_voice_services.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0
    assert "Check local E-Moti voice services." in completed.stdout
