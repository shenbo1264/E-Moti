from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path


def _write_reference(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    return path


def _write_regeneration_brief(path: Path, *, reference_path: Path) -> Path:
    payload = {
        "ok": True,
        "workflow_report_path": "artifacts\\portrait-video-workflow-report.json",
        "frame_qa_report_path": "artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.json",
        "set_id": "xingxi-vn-neutral-20260608-normalized",
        "source_pack_dir": str(reference_path.parents[1]),
        "reference_image_path": str(reference_path),
        "decision_state": "regenerate_ai_video",
        "frame_status": "ready_with_warnings",
        "frame_count": 60,
        "sampled_frame_count": 12,
        "size_mismatch_count": 0,
        "max_body_drift": 44.72,
        "preview_path": "artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.png",
        "blockers": [
            "workflow attention: body_drift_warnings",
            "max body drift 44.72 exceeds 16.0",
        ],
        "retry_prompt": "Previous attempt failed because body drift was too high. Use same canvas.",
        "negative_prompt": "No camera movement, zoom, crop, body recomposition, or pose change.",
        "prompt_constraints": [
            "Keep the exact same canvas, aspect ratio, crop, camera, and full-body framing as the reference.",
            "Only eyelids, tiny chest breathing, and slight hair-tip movement may animate.",
        ],
        "suggested_commands": [
            "python tools\\art\\portrait_video_frame_visual_qa.py artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized --preview artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.png --report artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.json",
        ],
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_bundle_portrait_video_retry_handoff_writes_zip_and_report(tmp_path: Path):
    from tools.art.bundle_portrait_video_retry_handoff import bundle_portrait_video_retry_handoff

    reference = _write_reference(tmp_path / "source-pack" / "reference" / "neutral_open.png")
    brief = _write_regeneration_brief(tmp_path / "regeneration-brief.json", reference_path=reference)

    report = bundle_portrait_video_retry_handoff(
        regeneration_brief_path=brief,
        output_dir=tmp_path / "retry-handoff",
        report_path=tmp_path / "retry-handoff-report.json",
    )

    assert report.ok is True
    assert report.set_id == "xingxi-vn-neutral-20260608-normalized"
    assert report.zip_path.endswith("xingxi-vn-neutral-20260608-normalized-retry.zip")
    assert Path(report.zip_path).is_file()
    assert (tmp_path / "retry-handoff-report.json").is_file()

    saved_report = json.loads((tmp_path / "retry-handoff-report.json").read_text(encoding="utf-8"))
    assert saved_report["ok"] is True
    assert saved_report["reference_image_path"] == str(reference)

    with zipfile.ZipFile(report.zip_path) as archive:
        names = set(archive.namelist())
        assert names == {
            "AI_VIDEO_RETRY_README.md",
            "negative_prompt.txt",
            "reference/neutral_open.png",
            "regeneration_brief.json",
            "retry_prompt.txt",
            "source_pack_reference.txt",
        }
        readme = archive.read("AI_VIDEO_RETRY_README.md").decode("utf-8")
        assert "xingxi-vn-neutral-20260608-normalized" in readme
        assert "Upload `reference/neutral_open.png`" in readme
        assert "Do not commit generated videos or rejected frames" in readme
        assert archive.read("retry_prompt.txt").decode("utf-8").startswith(
            "Previous attempt failed because body drift was too high"
        )
        assert "body recomposition" in archive.read("negative_prompt.txt").decode("utf-8")
        assert archive.read("reference/neutral_open.png") == reference.read_bytes()


def test_bundle_portrait_video_retry_handoff_cli_writes_report(tmp_path: Path):
    reference = _write_reference(tmp_path / "source-pack" / "reference" / "neutral_open.png")
    brief = _write_regeneration_brief(tmp_path / "regeneration-brief.json", reference_path=reference)
    output_dir = tmp_path / "retry-handoff"
    report_path = tmp_path / "retry-handoff-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/bundle_portrait_video_retry_handoff.py",
            str(brief),
            "--output-dir",
            str(output_dir),
            "--report",
            str(report_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert report_path.is_file()
    assert (output_dir / "xingxi-vn-neutral-20260608-normalized-retry.zip").is_file()


def test_bundle_portrait_video_retry_handoff_rejects_missing_reference(tmp_path: Path):
    from tools.art.bundle_portrait_video_retry_handoff import bundle_portrait_video_retry_handoff

    brief = _write_regeneration_brief(
        tmp_path / "regeneration-brief.json",
        reference_path=tmp_path / "missing" / "neutral_open.png",
    )

    report = bundle_portrait_video_retry_handoff(
        regeneration_brief_path=brief,
        output_dir=tmp_path / "retry-handoff",
    )

    assert report.ok is False
    assert "reference_image_path must point to an existing file" in report.errors
