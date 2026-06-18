from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


def write_blink_portrait_pack(pack_dir: Path, *, include_idle_frames: bool = False) -> Path:
    (pack_dir / "portraits").mkdir(parents=True)
    (pack_dir / "item_icons").mkdir()
    if include_idle_frames:
        (pack_dir / "motion_frames").mkdir()
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (32, 32), (40, 80, 120, 255)).save(pack_dir / "item_icons" / "snack.png")
    portrait_colors = {
        "neutral_open.png": (20, 80, 140, 255),
        "neutral_half.png": (80, 120, 160, 255),
        "neutral_closed.png": (140, 160, 200, 255),
        "smile.png": (50, 130, 90, 255),
        "thinking.png": (90, 90, 150, 255),
        "surprised.png": (160, 100, 80, 255),
        "sad.png": (70, 90, 120, 255),
        "sleepy.png": (110, 80, 130, 255),
    }
    for filename, color in portrait_colors.items():
        Image.new("RGBA", (256, 512), color).save(pack_dir / "portraits" / filename)
    if include_idle_frames:
        Image.new("RGBA", (256, 512), (24, 82, 142, 255)).save(pack_dir / "motion_frames" / "idle_0001.png")
        Image.new("RGBA", (256, 512), (28, 86, 146, 255)).save(pack_dir / "motion_frames" / "idle_0002.png")
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": pack_dir.name,
                "name": "Blink Candidate",
                "title": "Portrait smoke pack",
                "description": "Temporary portrait pack for smoke testing.",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Calm response."},
                "motion_labels": {"Default": "Idle"},
                "renderer": {
                    "backend": "portrait",
                    "portrait_manifest": "portrait_manifest.json",
                    "expression_map": {"focused": "thinking", "excited": "smile"},
                },
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 8,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "dialogue_style.json").write_text(
        json.dumps({"tone": "calm", "keywords": ["desktop"], "fallback_style": "short"}),
        encoding="utf-8",
    )
    (pack_dir / "shop_items.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "snack",
                    "name": "Snack",
                    "category": "food",
                    "icon": "item_icons/snack.png",
                    "price": 1,
                    "effects": {"mood": 1},
                }
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "portrait_manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "fallback_expression": "neutral",
                "anchor": "bottom_center",
                "default_scale": 1.0,
                "expressions": {
                    "neutral": {
                        "open": "portraits/neutral_open.png",
                        "blink_half": "portraits/neutral_half.png",
                        "blink_closed": "portraits/neutral_closed.png",
                    },
                    "smile": "portraits/smile.png",
                    "thinking": "portraits/thinking.png",
                    "surprised": "portraits/surprised.png",
                    "sad": "portraits/sad.png",
                    "sleepy": "portraits/sleepy.png",
                },
                "motion_frames": (
                    ["motion_frames/idle_0001.png", "motion_frames/idle_0002.png"]
                    if include_idle_frames
                    else []
                ),
                "animation": {
                    "blink": {"enabled": True, "min_interval_ms": 3000, "max_interval_ms": 7000},
                    "idle": {"enabled": include_idle_frames, "fps": 6},
                },
            }
        ),
        encoding="utf-8",
    )
    return pack_dir


def test_portrait_pack_smoke_validates_blink_sequence_and_writes_report(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from tools.portrait_pack_smoke import run_portrait_pack_smoke

    pack_dir = write_blink_portrait_pack(tmp_path / "xingxi_vn_blink_candidate")
    report_path = tmp_path / "portrait-smoke-report.json"

    report = run_portrait_pack_smoke(pack_dir, report_path=report_path)

    assert report.ok is True
    assert report.character_id == "xingxi_vn_blink_candidate"
    assert report.renderer_backend == "portrait"
    assert report.spirit_surface_visible is True
    assert report.sprite_fallback_visible is False
    assert report.blink_sequence == (
        "neutral_half.png",
        "neutral_closed.png",
        "neutral_half.png",
        "neutral_open.png",
    )
    assert report.runtime_manifest_referenced is False

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["blink_sequence"] == [
        "neutral_half.png",
        "neutral_closed.png",
        "neutral_half.png",
        "neutral_open.png",
    ]


def test_portrait_pack_smoke_reports_idle_motion_sequence(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from tools.portrait_pack_smoke import run_portrait_pack_smoke

    pack_dir = write_blink_portrait_pack(tmp_path / "xingxi_vn_idle_candidate", include_idle_frames=True)
    report_path = tmp_path / "portrait-smoke-report.json"

    report = run_portrait_pack_smoke(pack_dir, report_path=report_path)

    assert report.ok is True
    assert report.idle_sequence == ("idle_0001.png", "idle_0002.png")

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["idle_sequence"] == ["idle_0001.png", "idle_0002.png"]


def test_portrait_pack_smoke_cli_runs_from_repo_root_without_pythonpath(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pack_dir = write_blink_portrait_pack(tmp_path / "xingxi_vn_blink_candidate")
    report_path = tmp_path / "portrait-smoke-report.json"
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "tools/portrait_pack_smoke.py",
            str(pack_dir),
            "--report",
            str(report_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "portrait pack smoke ok:" in result.stdout
    assert json.loads(report_path.read_text(encoding="utf-8"))["ok"] is True
