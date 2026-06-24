from __future__ import annotations


def test_probe_voice_services_formats_ready_and_missing_statuses() -> None:
    from guanghe_companion.voice_service_control import (
        all_voice_services_ready,
        format_voice_service_statuses,
        probe_voice_services,
    )

    calls: list[tuple[str, float]] = []

    def fake_probe(url: str, timeout: float) -> tuple[bool, str]:
        calls.append((url, timeout))
        if "9882" in url:
            return False, "connection refused"
        if "9880" in url:
            return True, "HTTP 404"
        return True, "HTTP 200"

    statuses = probe_voice_services(timeout=0.5, probe=fake_probe)

    assert [status.service_id for status in statuses] == ["qwen3tts", "gptsovits", "sensevoice_asr"]
    assert [status.ok for status in statuses] == [True, False, True]
    assert all_voice_services_ready(statuses) is False
    assert calls == [
        ("http://127.0.0.1:9880/tts", 0.5),
        ("http://127.0.0.1:9882/", 0.5),
        ("http://127.0.0.1:8899/v1/models", 0.5),
    ]

    text = format_voice_service_statuses(statuses)

    assert "语音服务未就绪" in text
    assert "GPT-SoVITS" in text
    assert "connection refused" in text


def test_launch_missing_voice_services_starts_only_down_services(tmp_path) -> None:
    from guanghe_companion.voice_service_control import (
        VoiceServiceStatus,
        launch_missing_voice_services,
    )

    script_dir = tmp_path / "tools" / "voice_services"
    script_dir.mkdir(parents=True)
    gpt_script = script_dir / "start_ikaros_gptsovits_server.ps1"
    asr_script = script_dir / "start_sensevoice_asr_server.ps1"
    gpt_script.write_text("# gpt", encoding="utf-8")
    asr_script.write_text("# asr", encoding="utf-8")
    statuses = (
        VoiceServiceStatus("qwen3tts", "Qwen3TTS", True, "http://127.0.0.1:9880/tts", "HTTP 404"),
        VoiceServiceStatus("gptsovits", "GPT-SoVITS", False, "http://127.0.0.1:9882/", "down"),
        VoiceServiceStatus("sensevoice_asr", "SenseVoice ASR", False, "http://127.0.0.1:8899/v1/models", "down"),
    )
    commands: list[tuple[tuple[str, ...], str]] = []

    def fake_starter(command: tuple[str, ...], cwd: str) -> tuple[bool, str]:
        commands.append((command, cwd))
        return True, "started"

    results = launch_missing_voice_services(tmp_path, statuses=statuses, starter=fake_starter)

    assert [result.service_id for result in results] == ["qwen3tts", "gptsovits", "sensevoice_asr"]
    assert [result.started for result in results] == [False, True, True]
    assert len(commands) == 2
    assert str(gpt_script) in commands[0][0]
    assert "-NoWait" in commands[0][0]
    assert str(asr_script) in commands[1][0]
    assert "-Device" in commands[1][0]
    assert "cpu" in commands[1][0]
    assert commands[0][1] == str(tmp_path)
    assert commands[1][1] == str(tmp_path)


def test_launch_missing_voice_services_reports_missing_scripts(tmp_path) -> None:
    from guanghe_companion.voice_service_control import (
        VoiceServiceStatus,
        format_voice_service_launch_results,
        launch_missing_voice_services,
    )

    statuses = (
        VoiceServiceStatus("qwen3tts", "Qwen3TTS", False, "http://127.0.0.1:9880/tts", "down"),
    )
    commands: list[tuple[str, ...]] = []

    def fake_starter(command: tuple[str, ...], cwd: str) -> tuple[bool, str]:
        commands.append(command)
        return True, "started"

    results = launch_missing_voice_services(tmp_path, statuses=statuses, starter=fake_starter)

    assert commands == []
    assert results[0].started is False
    assert "启动脚本不存在" in results[0].message
    assert "Qwen3TTS" in format_voice_service_launch_results(results)
