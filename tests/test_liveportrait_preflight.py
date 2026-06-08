from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


REQUIRED_HUMAN_WEIGHT_PATHS = (
    "pretrained_weights/liveportrait/base_models/appearance_feature_extractor.pth",
    "pretrained_weights/liveportrait/base_models/motion_extractor.pth",
    "pretrained_weights/liveportrait/base_models/spade_generator.pth",
    "pretrained_weights/liveportrait/base_models/warping_module.pth",
    "pretrained_weights/liveportrait/landmark.onnx",
    "pretrained_weights/liveportrait/retargeting_models/stitching_retargeting_module.pth",
    "pretrained_weights/insightface/models/buffalo_l/2d106det.onnx",
    "pretrained_weights/insightface/models/buffalo_l/det_10g.onnx",
)


def _write_reference(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 512), (0, 0, 0, 0)).save(path)


def _write_source_pack(root: Path) -> Path:
    from tools.art.create_portrait_video_source_pack import create_portrait_video_source_pack

    source = root / "source" / "neutral_open.png"
    _write_reference(source)
    report = create_portrait_video_source_pack(
        source_image_path=source,
        output_root=root / "portrait-video-source",
        set_id="xingxi-vn-neutral-20260608",
        character_name="Xingxi",
        source_label="VN neutral candidate",
    )
    return Path(report.output_dir)


def _write_liveportrait_root(root: Path, *, with_weights: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "inference.py").write_text("print('fake liveportrait')\n", encoding="utf-8")
    (root / "app.py").write_text("print('fake gradio')\n", encoding="utf-8")
    (root / "requirements.txt").write_text("torch\n", encoding="utf-8")
    if with_weights:
        for relative_path in REQUIRED_HUMAN_WEIGHT_PATHS:
            weight_path = root / relative_path
            weight_path.parent.mkdir(parents=True, exist_ok=True)
            weight_path.write_bytes(b"fake weight")
    return root


def test_liveportrait_preflight_reports_ready_command(tmp_path: Path):
    from tools.art.inspect_liveportrait_preflight import inspect_liveportrait_preflight

    source_pack = _write_source_pack(tmp_path)
    liveportrait_root = _write_liveportrait_root(tmp_path / "LivePortrait")
    driving = tmp_path / "blink_driver.mp4"
    driving.write_bytes(b"fake video")
    metadata_before = (source_pack / "source_pack.json").read_text(encoding="utf-8")
    frame_files_before = tuple((source_pack / "frames").iterdir())

    report = inspect_liveportrait_preflight(
        source_pack,
        liveportrait_root=liveportrait_root,
        driving_path=driving,
        ffmpeg_path=sys.executable,
    )

    assert report.ok is True
    assert report.next_action == "run_liveportrait"
    assert report.source_image_path.endswith("reference\\neutral_open.png") or report.source_image_path.endswith(
        "reference/neutral_open.png"
    )
    assert report.driving_path == str(driving)
    assert report.ffmpeg_path == sys.executable
    assert report.missing_weight_paths == ()
    assert report.errors == ()
    assert "inference.py" in report.suggested_command
    assert " -s " in report.suggested_command
    assert " -d " in report.suggested_command
    assert (source_pack / "source_pack.json").read_text(encoding="utf-8") == metadata_before
    assert tuple((source_pack / "frames").iterdir()) == frame_files_before
    assert not (source_pack / "portrait_candidate.json").exists()


def test_liveportrait_preflight_blocks_missing_external_setup(tmp_path: Path):
    from tools.art.inspect_liveportrait_preflight import inspect_liveportrait_preflight

    source_pack = _write_source_pack(tmp_path)
    driving = tmp_path / "blink_driver.mp4"
    driving.write_bytes(b"fake video")

    report = inspect_liveportrait_preflight(
        source_pack,
        liveportrait_root=tmp_path / "missing-LivePortrait",
        driving_path=driving,
        ffmpeg_path=sys.executable,
    )

    assert report.ok is False
    assert report.next_action == "install_liveportrait"
    assert "liveportrait_root not found" in report.errors


def test_liveportrait_preflight_blocks_missing_weights_and_driving(tmp_path: Path):
    from tools.art.inspect_liveportrait_preflight import inspect_liveportrait_preflight

    source_pack = _write_source_pack(tmp_path)
    liveportrait_root = _write_liveportrait_root(tmp_path / "LivePortrait", with_weights=False)

    report = inspect_liveportrait_preflight(
        source_pack,
        liveportrait_root=liveportrait_root,
        driving_path="",
        ffmpeg_path=sys.executable,
    )

    assert report.ok is False
    assert report.next_action == "download_liveportrait_weights"
    assert "required pretrained weights are missing" in report.errors
    assert set(report.missing_weight_paths) == set(REQUIRED_HUMAN_WEIGHT_PATHS)
    assert "driving video or motion template is required" in report.errors


def test_liveportrait_preflight_cli_writes_report_and_markdown(tmp_path: Path):
    source_pack = _write_source_pack(tmp_path)
    liveportrait_root = _write_liveportrait_root(tmp_path / "LivePortrait")
    driving = tmp_path / "blink_driver.mp4"
    driving.write_bytes(b"fake video")
    report_path = tmp_path / "liveportrait-preflight.json"
    markdown_path = tmp_path / "liveportrait-preflight.md"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/inspect_liveportrait_preflight.py",
            str(source_pack),
            "--liveportrait-root",
            str(liveportrait_root),
            "--driving",
            str(driving),
            "--ffmpeg",
            sys.executable,
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
    assert payload["next_action"] == "run_liveportrait"
    assert report_path.is_file()
    assert markdown_path.is_file()
    assert "LivePortrait Preflight" in markdown_path.read_text(encoding="utf-8")
