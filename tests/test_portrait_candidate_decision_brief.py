from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def _write_candidate_manifest(root: Path, payload: object) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "portrait_candidate.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _write_halo_portrait(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (128, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((36, 24, 92, 232), radius=18, fill=(248, 248, 248, 128))
    draw.rounded_rectangle((42, 30, 86, 226), radius=14, fill=(40, 68, 120, 255))
    image.save(path)


def test_portrait_candidate_decision_brief_reports_blockers_and_warnings(tmp_path: Path):
    from tools.art.portrait_candidate_decision_brief import (
        build_portrait_candidate_decision_brief,
        render_portrait_candidate_decision_markdown,
    )

    candidate = tmp_path / "portrait-candidate"
    _write_halo_portrait(candidate / "portraits" / "neutral_open.png")
    manifest = _write_candidate_manifest(
        candidate,
        {
            "status": "candidate",
            "approval_required": True,
            "runtime_manifest_safe": False,
            "expressions": {"neutral": {"open": "portraits/neutral_open.png"}},
        },
    )

    brief = build_portrait_candidate_decision_brief(manifest)

    assert brief.ok is True
    assert brief.status == "candidate"
    assert brief.image_count == 1
    assert brief.decision_state == "needs_iteration"
    assert "candidate status is not approved" in brief.blockers
    assert "approval_required must be false before promotion" in brief.blockers
    assert "runtime_manifest_safe must be true before promotion" in brief.blockers
    assert "missing required expression: smile" in brief.blockers
    assert "neutral expression requires blink_half and blink_closed frames" in brief.blockers
    assert "neutral.open: light_edge_halo_risk" in brief.warnings
    assert brief.next_human_decisions == (
        "approve edge cleanup and expression/blink generation for this candidate, or reject it and regenerate",
    )
    markdown = render_portrait_candidate_decision_markdown(brief)
    assert "# Portrait Candidate Decision Brief" in markdown
    assert "Decision state: `needs_iteration`" in markdown
    assert "- candidate status is not approved" in markdown
    assert "- neutral.open: light_edge_halo_risk" in markdown
    assert "approve edge cleanup and expression/blink generation" in markdown


def test_portrait_candidate_decision_brief_accepts_ready_metadata_without_visual_warnings(tmp_path: Path):
    from tools.art.portrait_candidate_decision_brief import build_portrait_candidate_decision_brief

    candidate = tmp_path / "portrait-candidate"
    expressions: dict[str, object] = {}
    for expression in ("neutral", "smile", "thinking", "surprised", "sad", "sleepy"):
        image = Image.new("RGBA", (128, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((36, 24, 92, 232), radius=18, fill=(40, 70, 120, 255))
        path = candidate / "portraits" / f"{expression}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        expressions[expression] = f"portraits/{expression}.png"
    expressions["neutral"] = {
        "open": "portraits/neutral.png",
        "blink_half": "portraits/neutral_half.png",
        "blink_closed": "portraits/neutral_closed.png",
    }
    for filename in ("neutral_half.png", "neutral_closed.png"):
        image = Image.new("RGBA", (128, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((36, 24, 92, 232), radius=18, fill=(40, 70, 120, 255))
        image.save(candidate / "portraits" / filename)
    manifest = _write_candidate_manifest(
        candidate,
        {
            "status": "approved",
            "approval_required": False,
            "runtime_manifest_safe": True,
            "expressions": expressions,
        },
    )

    brief = build_portrait_candidate_decision_brief(manifest)

    assert brief.ok is True
    assert brief.decision_state == "ready_for_pack_promotion_review"
    assert brief.blockers == ()
    assert brief.warnings == ()


def test_portrait_candidate_decision_brief_cli_writes_json_from_repo_root(tmp_path: Path):
    candidate = tmp_path / "portrait-candidate"
    report_path = tmp_path / "decision-brief.json"
    markdown_path = tmp_path / "decision-brief.md"
    _write_halo_portrait(candidate / "portraits" / "neutral_open.png")
    manifest = _write_candidate_manifest(
        candidate,
        {"status": "candidate", "expressions": {"neutral": {"open": "portraits/neutral_open.png"}}},
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/portrait_candidate_decision_brief.py",
            str(manifest),
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
    assert payload["ok"] is True
    assert payload["decision_state"] == "needs_iteration"
    assert report_path.is_file()
    assert markdown_path.is_file()
    assert "Decision state: `needs_iteration`" in markdown_path.read_text(encoding="utf-8")
