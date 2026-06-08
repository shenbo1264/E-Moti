from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def _write_reference(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (240, 480), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((72, 28, 168, 456), radius=24, fill=(64, 92, 148, 255))
    draw.ellipse((84, 42, 156, 126), fill=(238, 210, 194, 255))
    image.save(path)


def _write_frame(path: Path, *, eye: str) -> None:
    image = Image.new("RGB", (240, 480), (245, 247, 250))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((72, 28, 168, 456), radius=24, fill=(64, 92, 148))
    draw.ellipse((84, 42, 156, 126), fill=(238, 210, 194))
    if eye == "open":
        draw.ellipse((103, 78, 115, 94), fill=(94, 66, 38))
        draw.ellipse((128, 78, 140, 94), fill=(94, 66, 38))
    elif eye == "closed":
        draw.line((102, 88, 116, 88), fill=(68, 50, 48), width=4)
        draw.line((127, 88, 141, 88), fill=(68, 50, 48), width=4)
    image.save(path)


def _write_frames(root: Path, *, count: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    eyes = ("open", "closed", "open", "open")
    for index, eye in enumerate(eyes[:count], start=1):
        _write_frame(root / f"frame_{index:04d}.png", eye=eye)


def _write_source_pack(root: Path, set_id: str, *, frame_count: int) -> Path:
    from tools.art.create_portrait_video_source_pack import create_portrait_video_source_pack

    source = root / "source" / f"{set_id}.png"
    _write_reference(source)
    report = create_portrait_video_source_pack(
        source_image_path=source,
        output_root=root / "portrait-video-source",
        set_id=set_id,
        character_name="Xingxi",
        source_label=set_id,
    )
    pack = Path(report.output_dir)
    if frame_count:
        _write_frames(pack / "frames", count=frame_count)
    return pack


def test_inspect_portrait_video_workflow_reports_next_actions(tmp_path: Path):
    from tools.art.bundle_portrait_video_source_packs import bundle_portrait_video_source_packs
    from tools.art.inspect_portrait_video_workflow import inspect_portrait_video_workflow

    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-waiting-20260608", frame_count=0)
    _write_source_pack(tmp_path, "xingxi-ready-20260608", frame_count=4)
    _write_source_pack(tmp_path, "xingxi-short-20260608", frame_count=2)
    handoff_dir = tmp_path / "handoff"
    bundle_portrait_video_source_packs(source_root=source_root, output_dir=handoff_dir)

    report = inspect_portrait_video_workflow(
        source_root=source_root,
        handoff_dir=handoff_dir,
        candidate_root=tmp_path / "candidates",
    )

    assert report.ok is True
    assert report.pack_count == 3
    actions = {item.set_id: item.next_action for item in report.items}
    assert actions == {
        "xingxi-ready-20260608": "process_frames",
        "xingxi-short-20260608": "export_more_frames",
        "xingxi-waiting-20260608": "generate_gemini_video",
    }
    handoff = {item.set_id: item.handoff_status for item in report.items}
    assert handoff == {
        "xingxi-ready-20260608": "present",
        "xingxi-short-20260608": "present",
        "xingxi-waiting-20260608": "present",
    }


def test_inspect_portrait_video_workflow_reports_missing_handoff_first(tmp_path: Path):
    from tools.art.inspect_portrait_video_workflow import inspect_portrait_video_workflow

    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-waiting-20260608", frame_count=0)

    report = inspect_portrait_video_workflow(
        source_root=source_root,
        handoff_dir=tmp_path / "handoff",
        candidate_root=tmp_path / "candidates",
    )

    assert report.ok is True
    assert report.missing_handoff_count == 1
    assert report.items[0].handoff_status == "missing"
    assert report.items[0].next_action == "bundle_handoff"


def test_inspect_portrait_video_workflow_cli_writes_report(tmp_path: Path):
    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-ready-20260608", frame_count=4)
    report_path = tmp_path / "workflow-status.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/inspect_portrait_video_workflow.py",
            str(source_root),
            "--handoff-dir",
            str(tmp_path / "handoff"),
            "--candidate-root",
            str(tmp_path / "candidates"),
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
    assert payload["pack_count"] == 1
    assert payload["items"][0]["next_action"] == "bundle_handoff"
    assert report_path.is_file()
