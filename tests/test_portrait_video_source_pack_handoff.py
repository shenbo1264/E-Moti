from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image


def _write_reference(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 512), (0, 0, 0, 0)).save(path)


def _write_source_pack(root: Path, set_id: str = "xingxi-vn-neutral-20260608") -> Path:
    from tools.art.create_portrait_video_source_pack import create_portrait_video_source_pack

    source = root / "source" / "neutral_open.png"
    _write_reference(source)
    report = create_portrait_video_source_pack(
        source_image_path=source,
        output_root=root / "portrait-video-source",
        set_id=set_id,
        character_name="Xingxi",
        source_label="VN neutral candidate",
    )
    return Path(report.output_dir)


def test_bundle_portrait_video_source_packs_writes_one_zip_per_source_pack(tmp_path: Path):
    from tools.art.bundle_portrait_video_source_packs import bundle_portrait_video_source_packs

    source_pack = _write_source_pack(tmp_path)
    output_dir = tmp_path / "handoff"

    report = bundle_portrait_video_source_packs(source_root=source_pack.parent, output_dir=output_dir)

    assert report.ok is True
    assert report.bundle_count == 1
    bundle = output_dir / "xingxi-vn-neutral-20260608.zip"
    assert bundle.is_file()
    assert report.bundles[0].zip_path == str(bundle)

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert names == {
            "AI_VIDEO_HANDOFF_README.md",
            "gemini_prompt.md",
            "provider_prompts.md",
            "source_pack.json",
            "reference/neutral_open.png",
        }
        prompt = archive.read("gemini_prompt.md").decode("utf-8")
        assert "Static camera" in prompt
        assert "one natural blink" in prompt
        provider_prompts = archive.read("provider_prompts.md").decode("utf-8")
        assert "Pika" in provider_prompts
        assert "Hailuo" in provider_prompts
        assert "Kling" in provider_prompts
        handoff = archive.read("AI_VIDEO_HANDOFF_README.md").decode("utf-8")
        assert "xingxi-vn-neutral-20260608" in handoff
        assert "Pika, Hailuo, Kling, PixVerse, Runway" in handoff
        assert "Put exported PNG frames back into" in handoff


def test_bundle_portrait_video_source_packs_rejects_unsafe_metadata_path(tmp_path: Path):
    from tools.art.bundle_portrait_video_source_packs import bundle_portrait_video_source_packs

    source_pack = _write_source_pack(tmp_path)
    metadata_path = source_pack / "source_pack.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload["reference_image"] = "../neutral_open.png"
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    report = bundle_portrait_video_source_packs(source_root=source_pack.parent, output_dir=tmp_path / "handoff")

    assert report.ok is False
    assert report.bundle_count == 0
    assert report.failed_count == 1
    assert any("source_pack.json.reference_image must be a safe relative path" in error for error in report.errors)
    assert not (tmp_path / "handoff" / "xingxi-vn-neutral-20260608.zip").exists()


def test_bundle_portrait_video_source_packs_cli_writes_report(tmp_path: Path):
    source_pack = _write_source_pack(tmp_path)
    output_dir = tmp_path / "handoff"
    report_path = tmp_path / "handoff-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/bundle_portrait_video_source_packs.py",
            str(source_pack.parent),
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
    assert payload["bundle_count"] == 1
    assert report_path.is_file()
    assert (output_dir / "xingxi-vn-neutral-20260608.zip").is_file()
