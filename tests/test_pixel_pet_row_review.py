from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from tools.art.review_pixel_pet_row_candidate import review_pixel_pet_row_candidate


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "art" / "review_pixel_pet_row_candidate.py"


def write_frames_root(
    root: Path,
    *,
    state: str = "idle",
    count: int = 6,
    method: str = "components",
) -> None:
    state_dir = root / state
    state_dir.mkdir(parents=True)
    frames = []
    for index in range(count):
        frame = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame)
        top = 60 + (index % 3)
        draw.rectangle((72, top, 120, top + 84), fill=(70, 100, 150, 255))
        draw.rectangle((82, top + 14, 110, top + 36), fill=(230, 240, 255, 255))
        if index == count // 2:
            draw.line((86, top + 24, 106, top + 24), fill=(40, 60, 90, 255), width=3)
        output = state_dir / f"{index:02d}.png"
        frame.save(output)
        frames.append(str(output))
    (root / "frames-manifest.json").write_text(
        json.dumps(
            {
                "ok": True,
                "chroma_key": {"hex": "#FF00FF", "rgb": [255, 0, 255], "threshold": 96.0},
                "rows": [{"state": state, "frames": frames, "method": method}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_review_pixel_pet_row_candidate_accepts_component_row_and_writes_outputs(
    tmp_path: Path,
) -> None:
    frames_root = tmp_path / "frames"
    report_path = tmp_path / "review" / "row-review.json"
    markdown_path = tmp_path / "review" / "row-review.md"
    preview_path = tmp_path / "review" / "row-review.png"
    write_frames_root(frames_root, method="components")

    report = review_pixel_pet_row_candidate(
        frames_root=frames_root,
        state="idle",
        expected_frames=6,
        require_components=True,
        report_path=report_path,
        markdown_path=markdown_path,
        preview_path=preview_path,
    )

    assert report.ok is True
    assert report.state == "idle"
    assert report.extraction_method == "components"
    assert report.errors == ()
    assert report_path.is_file()
    assert markdown_path.is_file()
    assert preview_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["asset_boundary"] == "ignored_candidate_only"
    assert payload["runtime_manifest_updated"] is False
    assert payload["actual_frames"] == 6


def test_review_pixel_pet_row_candidate_rejects_slot_row_when_components_required(
    tmp_path: Path,
) -> None:
    frames_root = tmp_path / "frames"
    write_frames_root(frames_root, method="slots")

    report = review_pixel_pet_row_candidate(
        frames_root=frames_root,
        state="idle",
        expected_frames=6,
        require_components=True,
    )

    assert report.ok is False
    assert "idle used extraction method slots; component extraction is required" in report.errors


def test_review_pixel_pet_row_candidate_tool_outputs_json_markdown_and_preview(
    tmp_path: Path,
) -> None:
    frames_root = tmp_path / "frames"
    output_dir = tmp_path / "review"
    write_frames_root(frames_root, method="components")

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            str(frames_root),
            "--state",
            "idle",
            "--expected-frames",
            "6",
            "--require-components",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert (output_dir / "idle-row-review.json").is_file()
    assert (output_dir / "idle-row-review.md").is_file()
    assert (output_dir / "idle-row-review.png").is_file()
