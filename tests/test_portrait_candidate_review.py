from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def _write_candidate(root: Path) -> Path:
    portrait = root / "portraits" / "neutral_open.png"
    portrait.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (128, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((36, 24, 92, 232), radius=18, fill=(248, 248, 248, 128))
    draw.rounded_rectangle((42, 30, 86, 226), radius=14, fill=(40, 68, 120, 255))
    image.save(portrait)
    manifest = root / "portrait_candidate.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "candidate",
                "approval_required": True,
                "runtime_manifest_safe": False,
                "expressions": {"neutral": {"open": "portraits/neutral_open.png"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


def test_review_portrait_candidate_writes_all_local_artifacts(tmp_path: Path):
    from tools.art.review_portrait_candidate import review_portrait_candidate

    manifest = _write_candidate(tmp_path / "candidate")
    output_dir = tmp_path / "candidate" / "review"

    report = review_portrait_candidate(manifest, output_dir=output_dir)

    assert report.ok is True
    assert report.decision_state == "needs_iteration"
    assert report.candidate_status == "candidate"
    assert report.validation_report["ok"] is True
    assert report.visual_qa_report["ok"] is True
    assert report.decision_brief["decision_state"] == "needs_iteration"
    assert (output_dir / "portrait-contact-sheet.png").is_file()
    assert (output_dir / "portrait-visual-qa.png").is_file()
    assert (output_dir / "portrait-visual-qa-report.json").is_file()
    assert (output_dir / "portrait-decision-brief.json").is_file()
    assert (output_dir / "portrait-decision-brief.md").is_file()
    assert "Decision state: `needs_iteration`" in (output_dir / "portrait-decision-brief.md").read_text(encoding="utf-8")


def test_review_portrait_candidate_cli_runs_from_repo_root(tmp_path: Path):
    manifest = _write_candidate(tmp_path / "candidate")
    output_dir = tmp_path / "candidate" / "review"
    report_path = tmp_path / "candidate" / "review-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/review_portrait_candidate.py",
            str(manifest),
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

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["decision_state"] == "needs_iteration"
    assert payload["review_outputs"]["decision_markdown"].endswith("portrait-decision-brief.md")
    assert report_path.is_file()
