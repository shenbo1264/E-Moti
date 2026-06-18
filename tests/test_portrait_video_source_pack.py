from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


def _write_reference(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 512), (0, 0, 0, 0)).save(path)


def test_create_portrait_video_source_pack_writes_reference_prompt_and_dropzones(tmp_path: Path):
    from tools.art.create_portrait_video_source_pack import create_portrait_video_source_pack

    source = tmp_path / "source" / "neutral_open.png"
    _write_reference(source)

    report = create_portrait_video_source_pack(
        source_image_path=source,
        output_root=tmp_path / "portrait-video-source",
        set_id="xingxi-vn-neutral-20260608",
        character_name="Xingxi",
        source_label="VN neutral candidate",
    )

    output = Path(report.output_dir)
    assert report.ok is True
    assert (output / "reference" / "neutral_open.png").is_file()
    assert (output / "frames" / "README.md").is_file()
    assert (output / "video" / "README.md").is_file()
    assert (output / "gemini_prompt.md").is_file()
    assert (output / "provider_prompts.md").is_file()
    assert (output / "source_pack.json").is_file()
    frames_readme = (output / "frames" / "README.md").read_text(encoding="utf-8")
    assert "After frame preflight reports `ready`" in frames_readme

    prompt = (output / "gemini_prompt.md").read_text(encoding="utf-8")
    assert "Static camera" in prompt
    assert "same character, outfit, pose, and proportions" in prompt
    assert "same canvas size and aspect ratio as the reference image" in prompt
    assert "Do not crop, zoom out, resize, reframe, or recompose the body" in prompt
    assert "Keep the hands, feet, shoulders, hips, and silhouette fixed" in prompt
    assert "Only eyelids, tiny chest breathing, and slight hair tips may move" in prompt
    assert "one natural blink" in prompt
    assert "subtle breathing" in prompt
    assert "no text" in prompt
    provider_prompts = (output / "provider_prompts.md").read_text(encoding="utf-8")
    assert "Pika" in provider_prompts
    assert "Hailuo" in provider_prompts
    assert "Kling" in provider_prompts
    assert "Vidu" in provider_prompts
    assert "LivePortrait" in provider_prompts
    assert "Use the same reference image" in provider_prompts
    assert "same canvas size and aspect ratio as the reference image" in provider_prompts
    assert "Do not crop, zoom out, resize, reframe, or recompose the body" in provider_prompts
    assert "Only eyelids, tiny chest breathing, and slight hair tips may move" in provider_prompts

    payload = json.loads((output / "source_pack.json").read_text(encoding="utf-8"))
    assert payload["set_id"] == "xingxi-vn-neutral-20260608"
    assert payload["source_label"] == "VN neutral candidate"
    assert payload["reference_image"] == "reference/neutral_open.png"
    assert payload["reference_size"] == [256, 512]
    assert payload["provider_prompts_path"] == "provider_prompts.md"
    assert payload["frames_dir"] == "frames"
    assert payload["video_dir"] == "video"


def test_create_portrait_video_source_pack_rejects_unsafe_set_id(tmp_path: Path):
    from tools.art.create_portrait_video_source_pack import create_portrait_video_source_pack

    source = tmp_path / "neutral_open.png"
    _write_reference(source)

    report = create_portrait_video_source_pack(
        source_image_path=source,
        output_root=tmp_path / "portrait-video-source",
        set_id="../unsafe",
    )

    assert report.ok is False
    assert "set_id must be a safe folder name" in report.errors
    assert not (tmp_path / "unsafe").exists()


def test_create_portrait_video_source_pack_cli_runs_from_repo_root(tmp_path: Path):
    source = tmp_path / "neutral_open.png"
    _write_reference(source)
    output_root = tmp_path / "portrait-video-source"

    result = subprocess.run(
        [
            sys.executable,
            "tools/art/create_portrait_video_source_pack.py",
            "--source-image",
            str(source),
            "--output-root",
            str(output_root),
            "--set-id",
            "xingxi-vn-neutral-20260608",
            "--character-name",
            "Xingxi",
            "--source-label",
            "VN neutral candidate",
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
    assert payload["prompt_path"].endswith("gemini_prompt.md")
    assert (output_root / "xingxi-vn-neutral-20260608" / "gemini_prompt.md").is_file()
