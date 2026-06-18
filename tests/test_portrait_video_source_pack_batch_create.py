from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def _write_portrait(path: Path, *, color: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (240, 480), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((72, 28, 168, 456), radius=24, fill=color)
    draw.ellipse((92, 44, 148, 112), fill=(238, 216, 202, 255))
    image.save(path)


def _write_candidate(root: Path) -> Path:
    portraits = root / "portraits"
    _write_portrait(portraits / "neutral_open.png", color=(80, 120, 180, 255))
    _write_portrait(portraits / "neutral_half.png", color=(78, 118, 178, 255))
    _write_portrait(portraits / "smile.png", color=(120, 160, 96, 255))
    (root / "portrait_candidate.json").write_text(
        json.dumps(
            {
                "status": "candidate",
                "expressions": {
                    "neutral": {
                        "open": "portraits/neutral_open.png",
                        "blink_half": "portraits/neutral_half.png",
                    },
                    "smile": "portraits/smile.png",
                },
            }
        ),
        encoding="utf-8",
    )
    return root / "portrait_candidate.json"


def test_create_portrait_video_source_packs_from_candidate_writes_one_folder_per_expression(tmp_path: Path):
    from tools.art.create_portrait_video_source_packs_from_candidate import (
        create_portrait_video_source_packs_from_candidate,
    )

    manifest = _write_candidate(tmp_path / "portrait-candidate")
    output_root = tmp_path / "portrait-video-source"

    report = create_portrait_video_source_packs_from_candidate(
        candidate_manifest_path=manifest,
        output_root=output_root,
        set_id_prefix="xingxi-vn",
        set_id_suffix="20260608",
        character_name="Xingxi",
        source_label_prefix="VN expression candidate",
    )

    assert report.ok is True
    assert report.created_count == 2
    assert report.failed_count == 0
    set_ids = {pack.set_id for pack in report.packs}
    assert set_ids == {"xingxi-vn-neutral-20260608", "xingxi-vn-smile-20260608"}

    neutral = output_root / "xingxi-vn-neutral-20260608"
    smile = output_root / "xingxi-vn-smile-20260608"
    assert (neutral / "reference" / "neutral_open.png").is_file()
    assert not (neutral / "reference" / "neutral_half.png").exists()
    assert (smile / "reference" / "smile.png").is_file()
    assert (neutral / "gemini_prompt.md").is_file()
    assert (smile / "frames" / "README.md").is_file()

    payload = json.loads((neutral / "source_pack.json").read_text(encoding="utf-8"))
    assert payload["reference_image"] == "reference/neutral_open.png"
    assert payload["source_label"] == "VN expression candidate neutral.open"


def test_create_portrait_video_source_packs_from_candidate_rejects_unsafe_expression_path(tmp_path: Path):
    from tools.art.create_portrait_video_source_packs_from_candidate import (
        create_portrait_video_source_packs_from_candidate,
    )

    candidate = tmp_path / "portrait-candidate"
    (candidate / "portrait_candidate.json").parent.mkdir(parents=True)
    (candidate / "portrait_candidate.json").write_text(
        json.dumps({"status": "candidate", "expressions": {"neutral": "../leak.png"}}),
        encoding="utf-8",
    )

    report = create_portrait_video_source_packs_from_candidate(
        candidate_manifest_path=candidate / "portrait_candidate.json",
        output_root=tmp_path / "portrait-video-source",
        set_id_prefix="xingxi-vn",
    )

    assert report.ok is False
    assert report.created_count == 0
    assert any("expressions.neutral.open must be a safe relative path" in error for error in report.errors)


def test_create_portrait_video_source_packs_from_candidate_cli_runs_from_repo_root(tmp_path: Path):
    manifest = _write_candidate(tmp_path / "portrait-candidate")
    output_root = tmp_path / "portrait-video-source"
    report_path = tmp_path / "source-pack-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/create_portrait_video_source_packs_from_candidate.py",
            str(manifest),
            "--output-root",
            str(output_root),
            "--set-id-prefix",
            "xingxi-vn",
            "--set-id-suffix",
            "20260608",
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
    assert payload["created_count"] == 2
    assert report_path.is_file()
    assert (output_root / "xingxi-vn-neutral-20260608" / "source_pack.json").is_file()
