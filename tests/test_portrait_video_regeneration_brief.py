from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_source_pack(root: Path) -> Path:
    source_pack_dir = root / "portrait-video-source" / "xingxi-vn-neutral-20260608-normalized"
    reference = source_pack_dir / "reference" / "neutral_open.png"
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_bytes(b"\x89PNG\r\n\x1a\n")
    (source_pack_dir / "source_pack.json").write_text(
        json.dumps(
            {
                "set_id": "xingxi-vn-neutral-20260608-normalized",
                "reference_image": "reference/neutral_open.png",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return source_pack_dir


def _write_workflow_report(path: Path, *, source_pack_dir: Path | None = None) -> Path:
    source_pack_dir_text = (
        str(source_pack_dir)
        if source_pack_dir is not None
        else "artifacts/portrait-video-source/xingxi-vn-neutral-20260608-normalized"
    )
    payload = {
        "ok": False,
        "source_root": "artifacts/portrait-video-source",
        "handoff_dir": "artifacts/portrait-video-handoff",
        "candidate_root": "artifacts",
        "pack_count": 1,
        "items": [
            {
                "set_id": "xingxi-vn-neutral-20260608-normalized",
                "source_pack_dir": source_pack_dir_text,
                "source_status": "ready_with_warnings",
                "frame_count": 60,
                "readable_frame_count": 60,
                "invalid_frame_count": 0,
                "size_mismatch_count": 0,
                "normalizable_size_mismatch_count": 0,
                "body_drift_warning_count": 60,
                "handoff_status": "present",
                "motion_candidate_status": "missing",
                "next_action": "review_frame_warnings",
                "source_next_action": "review_frame_warnings",
                "motion_next_action": "none",
                "attention_reasons": ["body_drift_warnings"],
                "suggested_commands": [
                    "python tools\\art\\portrait_video_frame_visual_qa.py artifacts\\portrait-video-source\\xingxi-vn-neutral-20260608-normalized --preview artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.png --report artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.json",
                    "python tools\\art\\portrait_video_regeneration_brief.py --workflow-report artifacts\\portrait-video-workflow-report.json --frame-qa-report artifacts\\portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.json --report artifacts\\portrait-video-regeneration-brief-xingxi-vn-neutral-20260608-normalized.json --markdown artifacts\\portrait-video-regeneration-brief-xingxi-vn-neutral-20260608-normalized.md",
                    "python tools\\art\\inspect_portrait_video_source_frames.py artifacts\\portrait-video-source --report artifacts\\portrait-video-frame-preflight.json",
                ],
                "warnings": ["frame_00006.png body drift 44.7 exceeds 16.0"],
                "errors": [],
            }
        ],
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_frame_qa_report(path: Path, *, max_body_drift: float = 44.72) -> Path:
    payload = {
        "ok": True,
        "set_id": "xingxi-vn-neutral-20260608-normalized",
        "source_pack_dir": "artifacts/portrait-video-source/xingxi-vn-neutral-20260608-normalized",
        "status": "ready_with_warnings",
        "next_action": "review_frame_warnings",
        "preview_path": "artifacts/portrait-video-frame-qa-xingxi-vn-neutral-20260608-normalized.png",
        "frame_count": 60,
        "sampled_frame_count": 12,
        "size_mismatch_count": 0,
        "max_body_drift": max_body_drift,
        "errors": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_portrait_video_regeneration_brief_rejects_drifted_frames(tmp_path: Path):
    from tools.art.portrait_video_regeneration_brief import (
        build_portrait_video_regeneration_brief,
        render_portrait_video_regeneration_markdown,
    )

    source_pack_dir = _write_source_pack(tmp_path)
    workflow = _write_workflow_report(tmp_path / "workflow.json", source_pack_dir=source_pack_dir)
    frame_qa = _write_frame_qa_report(tmp_path / "frame-qa.json")

    brief = build_portrait_video_regeneration_brief(
        workflow_report_path=workflow,
        frame_qa_report_path=frame_qa,
    )

    assert brief.ok is True
    assert brief.set_id == "xingxi-vn-neutral-20260608-normalized"
    assert brief.decision_state == "regenerate_ai_video"
    assert brief.source_pack_dir == str(source_pack_dir)
    assert brief.reference_image_path == str(source_pack_dir / "reference" / "neutral_open.png")
    assert brief.frame_status == "ready_with_warnings"
    assert brief.max_body_drift == 44.72
    assert "workflow attention: body_drift_warnings" in brief.blockers
    assert "max body drift 44.72 exceeds 16.0" in brief.blockers
    assert "Previous attempt failed because body drift was too high" in brief.retry_prompt
    assert "same canvas, same crop, same full-body framing" in brief.retry_prompt
    assert "only eyelids, tiny chest breathing, and slight hair-tip movement" in brief.retry_prompt
    assert "body recomposition" in brief.negative_prompt
    assert "camera movement" in brief.negative_prompt
    assert any("same canvas" in item for item in brief.prompt_constraints)
    assert any("Only eyelids" in item for item in brief.prompt_constraints)
    assert any("portrait_video_frame_visual_qa.py" in item for item in brief.suggested_commands)
    assert not any("portrait_video_regeneration_brief.py" in item for item in brief.suggested_commands)
    assert any("inspect_portrait_video_source_frames.py" in item for item in brief.suggested_commands)
    markdown = render_portrait_video_regeneration_markdown(brief)
    assert "# Portrait Video Regeneration Brief" in markdown
    assert "- Decision state: `regenerate_ai_video`" in markdown
    assert f"- Reference image: `{source_pack_dir / 'reference' / 'neutral_open.png'}`" in markdown
    assert "- Max body drift: `44.72`" in markdown
    assert "## Prompt Constraints" in markdown
    assert "## Provider Retry Prompt" in markdown
    assert "## Provider Negative Prompt" in markdown
    assert "Previous attempt failed because body drift was too high" in markdown
    assert "Only eyelids" in markdown


def test_portrait_video_regeneration_brief_accepts_explicit_set_id(tmp_path: Path):
    from tools.art.portrait_video_regeneration_brief import build_portrait_video_regeneration_brief

    workflow = _write_workflow_report(tmp_path / "workflow.json")

    brief = build_portrait_video_regeneration_brief(
        workflow_report_path=workflow,
        set_id="xingxi-vn-neutral-20260608-normalized",
    )

    assert brief.ok is True
    assert brief.set_id == "xingxi-vn-neutral-20260608-normalized"
    assert brief.decision_state == "regenerate_ai_video"
    assert brief.max_body_drift == 0.0
    assert "workflow attention: body_drift_warnings" in brief.blockers


def test_portrait_video_regeneration_brief_cli_writes_outputs(tmp_path: Path):
    workflow = _write_workflow_report(tmp_path / "workflow.json")
    frame_qa = _write_frame_qa_report(tmp_path / "frame-qa.json")
    report_path = tmp_path / "regeneration-brief.json"
    markdown_path = tmp_path / "regeneration-brief.md"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/portrait_video_regeneration_brief.py",
            "--workflow-report",
            str(workflow),
            "--frame-qa-report",
            str(frame_qa),
            "--report",
            str(report_path),
            "--markdown",
            str(markdown_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["decision_state"] == "regenerate_ai_video"
    assert "Previous attempt failed because body drift was too high" in payload["retry_prompt"]
    assert "body recomposition" in payload["negative_prompt"]
    assert report_path.is_file()
    assert markdown_path.is_file()
    assert "Prompt Constraints" in markdown_path.read_text(encoding="utf-8")
