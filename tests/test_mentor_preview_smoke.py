from __future__ import annotations

import json
from pathlib import Path


REQUIRED_VOICE_SCRIPTS = (
    "preflight_voice_services.py",
    "qwen3_tts_local_server.py",
    "start_qwen3_tts_server.ps1",
    "start_ikaros_gptsovits_server.ps1",
    "start_sensevoice_asr_server.ps1",
)

REQUIRED_CHARACTER_IDS = (
    "xingxi_pixel_pet",
    "ikaros_pixel_pet",
    "nairong_pixel_pet",
)


def _write_packaged_app(root: Path) -> Path:
    app_dir = root / "dist" / "E-Moti"
    voice_dir = app_dir / "_internal" / "voice_services"
    voice_dir.mkdir(parents=True)
    for script in REQUIRED_VOICE_SCRIPTS:
        (voice_dir / script).write_text(f"# {script}\n", encoding="utf-8")

    character_root = app_dir / "_internal" / "assets" / "companion"
    for character_id in REQUIRED_CHARACTER_IDS:
        pack_dir = character_root / character_id
        pack_dir.mkdir(parents=True)
        (pack_dir / "character.json").write_text(
            json.dumps({"character_id": character_id}, ensure_ascii=False),
            encoding="utf-8",
        )

    (app_dir / "E-Moti.exe").write_bytes(b"MZ" + b"0" * 128)
    return app_dir


def test_mentor_preview_smoke_copies_package_and_launches_control_panel_and_pet_mode(tmp_path: Path):
    from tools.mentor_preview_smoke import run_mentor_preview_smoke

    app_dir = _write_packaged_app(tmp_path / "source")
    launches: list[dict[str, object]] = []

    def fake_launch(exe_path, args, env, seconds):
        launches.append(
            {
                "exe_path": exe_path,
                "args": tuple(args),
                "user_data_dir": env.get("E_MOTI_USER_DATA_DIR"),
                "seconds": seconds,
            }
        )
        return {
            "ok": True,
            "args": list(args),
            "seconds": seconds,
            "exit_code": None,
            "error": "",
        }

    report = run_mentor_preview_smoke(
        app_dir=app_dir,
        work_root=tmp_path / "mentor-smoke",
        seconds=0.1,
        launcher=fake_launch,
    )

    working_app_dir = tmp_path / "mentor-smoke" / "E-Moti-portable"
    user_data_dir = tmp_path / "mentor-smoke" / "user-data"
    assert report.ok is True
    assert report.working_app_dir == str(working_app_dir)
    assert (working_app_dir / "E-Moti.exe").is_file()
    assert len(launches) == 2
    assert launches[0]["args"] == ()
    assert launches[1]["args"] == ("--pet-mode",)
    assert launches[0]["exe_path"] == working_app_dir / "E-Moti.exe"
    assert launches[0]["user_data_dir"] == str(user_data_dir)
    assert report.voice_runtime_present is False
    assert "portable voice_runtime not found" in report.warnings


def test_mentor_preview_smoke_rejects_missing_required_packaged_files(tmp_path: Path):
    from tools.mentor_preview_smoke import run_mentor_preview_smoke

    app_dir = _write_packaged_app(tmp_path / "source")
    (app_dir / "_internal" / "voice_services" / "start_sensevoice_asr_server.ps1").unlink()
    (app_dir / "_internal" / "assets" / "companion" / "ikaros_pixel_pet" / "character.json").unlink()
    launch_called = False

    def fake_launch(exe_path, args, env, seconds):
        nonlocal launch_called
        launch_called = True
        return {"ok": True, "args": list(args), "seconds": seconds, "exit_code": None, "error": ""}

    report = run_mentor_preview_smoke(
        app_dir=app_dir,
        work_root=tmp_path / "mentor-smoke",
        seconds=0.1,
        launcher=fake_launch,
    )

    assert report.ok is False
    assert launch_called is False
    assert "missing packaged file: _internal/voice_services/start_sensevoice_asr_server.ps1" in report.errors
    assert "missing packaged file: _internal/assets/companion/ikaros_pixel_pet/character.json" in report.errors


def test_mentor_preview_smoke_cli_writes_json_report(tmp_path: Path, monkeypatch):
    from tools import mentor_preview_smoke

    app_dir = _write_packaged_app(tmp_path / "source")
    report_path = tmp_path / "report.json"

    monkeypatch.setattr(
        mentor_preview_smoke,
        "_launch_frozen_app",
        lambda exe_path, args, env, seconds: {
            "ok": True,
            "args": list(args),
            "seconds": seconds,
            "exit_code": None,
            "error": "",
        },
    )

    code = mentor_preview_smoke.main(
        [
            "--app-dir",
            str(app_dir),
            "--work-root",
            str(tmp_path / "mentor-smoke"),
            "--seconds",
            "0.1",
            "--report",
            str(report_path),
        ]
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["ok"] is True
    assert payload["launches"][0]["mode"] == "control_panel"
    assert payload["launches"][1]["mode"] == "pet_mode"
