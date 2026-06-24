from __future__ import annotations

import json
import zipfile
from pathlib import Path


def test_course_submission_package_excludes_voice_runtime_and_overlays_private_config(tmp_path: Path):
    from tools.build_course_submission_package import build_course_submission_package

    app_dir = tmp_path / "dist" / "E-Moti"
    (app_dir / "_internal" / "voice_services").mkdir(parents=True)
    (app_dir / "voice_runtime").mkdir()
    (app_dir / "voice_runtime" / "huge.bin").write_bytes(b"large")
    (app_dir / "E-Moti.exe").write_bytes(b"MZ")
    private_config = tmp_path / "private_submission_config"
    private_config.mkdir()
    (private_config / "expression_settings.json").write_text(
        '{"enabled": true, "provider": "deepseek", "api_key": "sk-very-secret"}',
        encoding="utf-8",
    )

    report = build_course_submission_package(
        app_dir=app_dir,
        private_config_dir=private_config,
        output_dir=tmp_path / "dist" / "E-Moti-course-submission",
        zip_path=tmp_path / "dist" / "E-Moti-course-submission.zip",
    )

    output_dir = tmp_path / "dist" / "E-Moti-course-submission"
    assert report.ok is True
    assert report.private_config_files == ("expression_settings.json",)
    assert report.ai_expression_settings["enabled"] is True
    assert report.ai_expression_settings["provider"] == "deepseek"
    assert report.ai_expression_settings["model"] == "deepseek-v4-flash"
    assert report.ai_expression_settings["api_key_set"] is True
    assert report.ai_expression_settings["ready"] is True
    assert "sk-very-secret" not in json.dumps(report.to_dict(), ensure_ascii=False)
    assert (output_dir / "E-Moti.exe").is_file()
    assert not (output_dir / "voice_runtime").exists()
    assert (output_dir / "user_data" / "expression_settings.json").is_file()
    assert (tmp_path / "dist" / "E-Moti-course-submission.zip").is_file()

    with zipfile.ZipFile(tmp_path / "dist" / "E-Moti-course-submission.zip") as archive:
        names = set(archive.namelist())
    assert "E-Moti.exe" in names
    assert "user_data/expression_settings.json" in names
    assert "voice_runtime/huge.bin" not in names


def test_course_submission_package_accepts_missing_private_config_dir(tmp_path: Path):
    from tools.build_course_submission_package import build_course_submission_package

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "E-Moti.exe").write_bytes(b"MZ")

    report = build_course_submission_package(
        app_dir=app_dir,
        private_config_dir=tmp_path / "missing-private-config",
        output_dir=tmp_path / "out",
        zip_path=tmp_path / "out.zip",
    )

    assert report.ok is True
    assert report.private_config_files == ()
    assert "private config directory not found" in report.warnings
    assert (tmp_path / "out.zip").is_file()


def test_course_submission_package_rejects_nested_private_config_paths(tmp_path: Path):
    from tools.build_course_submission_package import build_course_submission_package

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "E-Moti.exe").write_bytes(b"MZ")
    private_config = tmp_path / "private"
    (private_config / "nested").mkdir(parents=True)
    (private_config / "nested" / "secret.json").write_text("{}", encoding="utf-8")

    report = build_course_submission_package(
        app_dir=app_dir,
        private_config_dir=private_config,
        output_dir=tmp_path / "out",
        zip_path=tmp_path / "out.zip",
    )

    assert report.ok is False
    assert "private config file must be at top level: nested/secret.json" in report.errors
    assert not (tmp_path / "out.zip").exists()


def test_course_submission_package_rejects_unapproved_private_config_filename(tmp_path: Path):
    from tools.build_course_submission_package import build_course_submission_package

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "E-Moti.exe").write_bytes(b"MZ")
    private_config = tmp_path / "private"
    private_config.mkdir()
    (private_config / ".env").write_text("DEEPSEEK_API_KEY=secret", encoding="utf-8")

    report = build_course_submission_package(
        app_dir=app_dir,
        private_config_dir=private_config,
        output_dir=tmp_path / "out",
        zip_path=tmp_path / "out.zip",
    )

    assert report.ok is False
    assert "private config filename is not allowed: .env" in report.errors


def test_course_submission_package_cli_writes_report(tmp_path: Path):
    from tools import build_course_submission_package

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "E-Moti.exe").write_bytes(b"MZ")
    private_config = tmp_path / "private"
    private_config.mkdir()
    (private_config / "capability_settings.json").write_text("{}", encoding="utf-8")
    report_path = tmp_path / "report.json"

    code = build_course_submission_package.main(
        [
            "--app-dir",
            str(app_dir),
            "--private-config-dir",
            str(private_config),
            "--output-dir",
            str(tmp_path / "out"),
            "--zip-path",
            str(tmp_path / "out.zip"),
            "--report",
            str(report_path),
        ]
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["ok"] is True
    assert payload["private_config_files"] == ["capability_settings.json"]
