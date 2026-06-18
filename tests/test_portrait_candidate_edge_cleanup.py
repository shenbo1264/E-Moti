from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def _write_halo_candidate(root: Path) -> Path:
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


def test_clean_portrait_candidate_edges_clones_and_reduces_light_halo(tmp_path: Path):
    from tools.art.clean_portrait_candidate_edges import clean_portrait_candidate_edges
    from tools.art.portrait_candidate_visual_qa import inspect_portrait_candidate_visual_qa

    source_dir = tmp_path / "portrait-candidate"
    manifest = _write_halo_candidate(source_dir)
    before = inspect_portrait_candidate_visual_qa(manifest)
    before_metric = before.images[0]["light_edge_alpha_pixel_count"]

    output_dir = tmp_path / "portrait-candidate-cleaned"
    report = clean_portrait_candidate_edges(manifest, output_dir, report_path=output_dir / "edge-cleanup-report.json")

    assert report.ok is True
    assert report.cleaned_image_count == 1
    assert report.changed_pixel_count > 0
    assert report.errors == ()
    assert (output_dir / "portrait_candidate.json").is_file()
    assert (output_dir / "edge-cleanup-report.json").is_file()
    assert json.loads((output_dir / "portrait_candidate.json").read_text(encoding="utf-8"))["status"] == "candidate"

    after = inspect_portrait_candidate_visual_qa(output_dir / "portrait_candidate.json")
    after_metric = after.images[0]["light_edge_alpha_pixel_count"]
    assert after_metric < before_metric
    assert "light_edge_halo_risk" not in after.images[0]["warnings"]

    with Image.open(source_dir / "portraits" / "neutral_open.png") as original:
        payload = original.convert("RGBA").tobytes()
    assert any(
        payload[index + 3] == 128 and payload[index] >= 220 and payload[index + 1] >= 220 and payload[index + 2] >= 220
        for index in range(0, len(payload), 4)
    )


def test_clean_portrait_candidate_edges_rejects_existing_output_without_overwrite(tmp_path: Path):
    from tools.art.clean_portrait_candidate_edges import clean_portrait_candidate_edges

    manifest = _write_halo_candidate(tmp_path / "portrait-candidate")
    output_dir = tmp_path / "portrait-candidate-cleaned"
    output_dir.mkdir()

    report = clean_portrait_candidate_edges(manifest, output_dir)

    assert report.ok is False
    assert "output_dir already exists" in report.errors


def test_clean_portrait_candidate_edges_cli_runs_from_repo_root(tmp_path: Path):
    manifest = _write_halo_candidate(tmp_path / "portrait-candidate")
    output_dir = tmp_path / "portrait-candidate-cleaned"
    report_path = output_dir / "edge-cleanup-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/clean_portrait_candidate_edges.py",
            str(manifest),
            "--output",
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
    assert payload["cleaned_image_count"] == 1
    assert report_path.is_file()
