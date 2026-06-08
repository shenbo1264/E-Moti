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


def _write_frame(path: Path, *, eye: str, size: tuple[int, int] = (240, 480)) -> None:
    image = Image.new("RGB", size, (245, 247, 250))
    draw = ImageDraw.Draw(image)
    scale_x = size[0] / 240
    scale_y = size[1] / 480
    draw.rounded_rectangle(
        (
            int(72 * scale_x),
            int(28 * scale_y),
            int(168 * scale_x),
            int(456 * scale_y),
        ),
        radius=max(4, int(24 * min(scale_x, scale_y))),
        fill=(64, 92, 148),
    )
    draw.ellipse(
        (
            int(84 * scale_x),
            int(42 * scale_y),
            int(156 * scale_x),
            int(126 * scale_y),
        ),
        fill=(238, 210, 194),
    )
    if eye == "open":
        draw.ellipse(
            (
                int(103 * scale_x),
                int(78 * scale_y),
                int(115 * scale_x),
                int(94 * scale_y),
            ),
            fill=(94, 66, 38),
        )
        draw.ellipse(
            (
                int(128 * scale_x),
                int(78 * scale_y),
                int(140 * scale_x),
                int(94 * scale_y),
            ),
            fill=(94, 66, 38),
        )
    elif eye == "closed":
        draw.line(
            (
                int(102 * scale_x),
                int(88 * scale_y),
                int(116 * scale_x),
                int(88 * scale_y),
            ),
            fill=(68, 50, 48),
            width=4,
        )
        draw.line(
            (
                int(127 * scale_x),
                int(88 * scale_y),
                int(141 * scale_x),
                int(88 * scale_y),
            ),
            fill=(68, 50, 48),
            width=4,
        )
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
    from tools.art.inspect_portrait_video_workflow import (
        inspect_portrait_video_workflow,
        render_portrait_video_workflow_markdown,
    )

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
        "xingxi-waiting-20260608": "generate_ai_video",
    }
    handoff = {item.set_id: item.handoff_status for item in report.items}
    assert handoff == {
        "xingxi-ready-20260608": "present",
        "xingxi-short-20260608": "present",
        "xingxi-waiting-20260608": "present",
    }
    markdown = render_portrait_video_workflow_markdown(report)
    assert "| Set | Source Status | Frames | Handoff | Motion Candidate | Next Action |" in markdown
    assert "| xingxi-ready-20260608 | ready | 4 | present | missing | process_frames |" in markdown
    assert "| xingxi-short-20260608 | insufficient_frames | 2 | present | missing | export_more_frames |" in markdown
    assert "| xingxi-waiting-20260608 | waiting_for_frames | 0 | present | missing | generate_ai_video |" in markdown
    waiting_item = next(item for item in report.items if item.set_id == "xingxi-waiting-20260608")
    assert any("inspect_liveportrait_preflight.py" in command for command in waiting_item.suggested_commands)
    assert any("tmp\\liveportrait_research\\LivePortrait" in command for command in waiting_item.suggested_commands)
    assert any(
        "tmp\\liveportrait_research\\drivers\\xingxi-waiting-20260608-blink-driver.mp4" in command
        for command in waiting_item.suggested_commands
    )
    assert "inspect_liveportrait_preflight.py" in markdown


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


def test_inspect_portrait_video_workflow_uses_frame_preflight_for_invalid_frames(tmp_path: Path):
    from tools.art.bundle_portrait_video_source_packs import bundle_portrait_video_source_packs
    from tools.art.inspect_portrait_video_workflow import inspect_portrait_video_workflow

    source_root = tmp_path / "portrait-video-source"
    pack = _write_source_pack(tmp_path, "xingxi-invalid-20260609", frame_count=0)
    frames = pack / "frames"
    _write_frame(frames / "frame_0001.png", eye="open")
    _write_frame(frames / "frame_0002.png", eye="closed")
    (frames / "frame_0003.png").write_text("not a png", encoding="utf-8")
    handoff_dir = tmp_path / "handoff"
    bundle_portrait_video_source_packs(source_root=source_root, output_dir=handoff_dir)

    report = inspect_portrait_video_workflow(
        source_root=source_root,
        handoff_dir=handoff_dir,
        candidate_root=tmp_path / "candidates",
    )

    assert report.ok is False
    item = report.items[0]
    assert item.source_status == "invalid_frames"
    assert item.frame_count == 3
    assert item.readable_frame_count == 2
    assert item.invalid_frame_count == 1
    assert item.next_action == "replace_invalid_frames"
    assert any("frame_0003.png" in error for error in item.errors)


def test_inspect_portrait_video_workflow_uses_frame_preflight_for_size_warnings(tmp_path: Path):
    from tools.art.bundle_portrait_video_source_packs import bundle_portrait_video_source_packs
    from tools.art.inspect_portrait_video_workflow import (
        inspect_portrait_video_workflow,
        render_portrait_video_workflow_markdown,
    )

    source_root = tmp_path / "portrait-video-source"
    pack = _write_source_pack(tmp_path, "xingxi-warning-20260609", frame_count=0)
    frames = pack / "frames"
    _write_frame(frames / "frame_0001.png", eye="open")
    _write_frame(frames / "frame_0002.png", eye="closed", size=(320, 480))
    _write_frame(frames / "frame_0003.png", eye="open")
    handoff_dir = tmp_path / "handoff"
    bundle_portrait_video_source_packs(source_root=source_root, output_dir=handoff_dir)

    report = inspect_portrait_video_workflow(
        source_root=source_root,
        handoff_dir=handoff_dir,
        candidate_root=tmp_path / "candidates",
    )

    assert report.ok is True
    item = report.items[0]
    assert item.source_status == "ready_with_warnings"
    assert item.readable_frame_count == 3
    assert item.size_mismatch_count == 1
    assert item.next_action == "review_frame_warnings"
    assert any("frame_0002.png size 320x480 differs from reference 240x480" in warning for warning in item.warnings)
    assert "| xingxi-warning-20260609 | ready_with_warnings | 3 | present | missing | review_frame_warnings |" in render_portrait_video_workflow_markdown(report)


def test_inspect_portrait_video_workflow_recommends_normalization_for_same_aspect_size_warnings(tmp_path: Path):
    from tools.art.bundle_portrait_video_source_packs import bundle_portrait_video_source_packs
    from tools.art.inspect_portrait_video_workflow import (
        inspect_portrait_video_workflow,
        render_portrait_video_workflow_markdown,
    )

    source_root = tmp_path / "portrait-video-source"
    pack = _write_source_pack(tmp_path, "xingxi-lowres-20260609", frame_count=0)
    frames = pack / "frames"
    _write_frame(frames / "frame_0001.png", eye="open", size=(120, 240))
    _write_frame(frames / "frame_0002.png", eye="closed", size=(120, 240))
    _write_frame(frames / "frame_0003.png", eye="open", size=(120, 240))
    handoff_dir = tmp_path / "handoff"
    bundle_portrait_video_source_packs(source_root=source_root, output_dir=handoff_dir)

    report = inspect_portrait_video_workflow(
        source_root=source_root,
        handoff_dir=handoff_dir,
        candidate_root=tmp_path / "candidates",
    )

    assert report.ok is True
    item = report.items[0]
    assert item.source_status == "ready_with_warnings"
    assert item.size_mismatch_count == 3
    assert item.normalizable_size_mismatch_count == 3
    assert item.attention_reasons == ("normalizable_size_mismatch",)
    assert item.next_action == "normalize_frames"
    assert any("normalize_portrait_video_source_frames.py" in command for command in item.suggested_commands)
    assert any("inspect_portrait_video_source_frames.py" in command for command in item.suggested_commands)
    markdown = render_portrait_video_workflow_markdown(report)
    assert "| xingxi-lowres-20260609 | ready_with_warnings | 3 | present | missing | normalize_frames |" in markdown
    assert "- `xingxi-lowres-20260609`: `normalizable_size_mismatch`" in markdown
    assert "## Suggested Commands" in markdown
    assert "normalize_portrait_video_source_frames.py" in markdown


def test_inspect_portrait_video_workflow_surfaces_failed_motion_extraction(tmp_path: Path):
    from tools.art.bundle_portrait_video_source_packs import bundle_portrait_video_source_packs
    from tools.art.inspect_portrait_video_workflow import (
        inspect_portrait_video_workflow,
        render_portrait_video_workflow_markdown,
    )

    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-failed-motion-20260609", frame_count=4)
    handoff_dir = tmp_path / "handoff"
    bundle_portrait_video_source_packs(source_root=source_root, output_dir=handoff_dir)
    failed_candidate = tmp_path / "candidates" / "portrait-candidate-xingxi-failed-motion-20260609-motion"
    failed_candidate.mkdir(parents=True)
    (failed_candidate / "candidate-motion-frame-report.json").write_text(
        json.dumps(
            {
                "ok": False,
                "errors": ["not enough stable frames after body drift filtering"],
            }
        ),
        encoding="utf-8",
    )

    report = inspect_portrait_video_workflow(
        source_root=source_root,
        handoff_dir=handoff_dir,
        candidate_root=tmp_path / "candidates",
    )

    assert report.ok is False
    item = report.items[0]
    assert item.motion_candidate_status == "failed"
    assert item.attention_reasons == ("failed_motion_extraction",)
    assert item.next_action == "regenerate_ai_video"
    assert "motion extraction failed: not enough stable frames after body drift filtering" in item.errors
    assert "| xingxi-failed-motion-20260609 | ready | 4 | present | failed | regenerate_ai_video |" in render_portrait_video_workflow_markdown(report)


def test_inspect_portrait_video_workflow_splits_source_and_motion_next_actions(tmp_path: Path):
    from tools.art.bundle_portrait_video_source_packs import bundle_portrait_video_source_packs
    from tools.art.inspect_portrait_video_workflow import (
        inspect_portrait_video_workflow,
        render_portrait_video_workflow_markdown,
    )

    source_root = tmp_path / "portrait-video-source"
    pack = _write_source_pack(tmp_path, "xingxi-lowres-failed-20260609", frame_count=0)
    frames = pack / "frames"
    _write_frame(frames / "frame_0001.png", eye="open", size=(120, 240))
    _write_frame(frames / "frame_0002.png", eye="closed", size=(120, 240))
    _write_frame(frames / "frame_0003.png", eye="open", size=(120, 240))
    handoff_dir = tmp_path / "handoff"
    bundle_portrait_video_source_packs(source_root=source_root, output_dir=handoff_dir)
    failed_candidate = tmp_path / "candidates" / "portrait-candidate-xingxi-lowres-failed-20260609-motion"
    failed_candidate.mkdir(parents=True)
    (failed_candidate / "candidate-motion-frame-report.json").write_text(
        json.dumps({"ok": False, "errors": ["not enough stable frames after body drift filtering"]}),
        encoding="utf-8",
    )

    report = inspect_portrait_video_workflow(
        source_root=source_root,
        handoff_dir=handoff_dir,
        candidate_root=tmp_path / "candidates",
    )

    item = report.items[0]
    assert item.source_next_action == "normalize_frames"
    assert item.motion_next_action == "regenerate_ai_video"
    assert item.next_action == "regenerate_ai_video"
    assert item.attention_reasons == ("normalizable_size_mismatch", "failed_motion_extraction")
    assert any("normalize_portrait_video_source_frames.py" in command for command in item.suggested_commands)
    assert any("inspect_portrait_video_source_frames.py" in command for command in item.suggested_commands)
    markdown = render_portrait_video_workflow_markdown(report)
    assert "| xingxi-lowres-failed-20260609 | normalize_frames | regenerate_ai_video |" in markdown


def test_inspect_portrait_video_workflow_cli_writes_report(tmp_path: Path):
    source_root = tmp_path / "portrait-video-source"
    _write_source_pack(tmp_path, "xingxi-ready-20260608", frame_count=4)
    report_path = tmp_path / "workflow-status.json"
    markdown_path = tmp_path / "workflow-status.md"

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
    assert payload["pack_count"] == 1
    assert payload["items"][0]["next_action"] == "bundle_handoff"
    assert report_path.is_file()
    assert markdown_path.is_file()
    assert "bundle_handoff" in markdown_path.read_text(encoding="utf-8")
