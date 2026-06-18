import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "validate_character_pack.py"


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_live2d_pack(root, *, with_model=True):
    pack_dir = root / "xingxi_live2d"
    (pack_dir / "item_icons").mkdir(parents=True)
    (pack_dir / "live2d").mkdir()
    Image.new("RGBA", (1536, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(pack_dir / "item_icons" / "snack.png")
    if with_model:
        (pack_dir / "live2d" / "Xingxi.model3.json").write_text("{}", encoding="utf-8")
    _write_json(
        pack_dir / "character.json",
        {
            "character_id": "xingxi_live2d",
            "name": "Xingxi",
            "title": "Live2D companion",
            "description": "Live2D validation pack",
            "spritesheet": "spritesheet.png",
            "motion_manifest": "motion_manifest.json",
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "Calm response"},
            "motion_labels": {"Default": "Idle"},
            "renderer": {
                "backend": "live2d_web",
                "model": "live2d/Xingxi.model3.json",
                "expression_map": {
                    "calm": "F01",
                    "excited": "F02",
                    "surprised": "F03",
                    "sleepy": "F05",
                    "sadness": "F04",
                    "focused": "F06",
                },
                "motion_map": {
                    "Default": "Idle",
                    "Play": "TapBody",
                    "Raised": "TapBody",
                    "TouchHead": "TapHead",
                    "Sleep": "Sleep",
                },
            },
        },
    )
    _write_json(
        pack_dir / "dialogue_style.json",
        {"tone": "calm", "keywords": ["star"], "fallback_style": "short"},
    )
    _write_json(
        pack_dir / "motion_manifest.json",
        {
            "sheet_columns": 8,
            "sheet_rows": 9,
            "frame_width": 192,
            "frame_height": 208,
            "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
        },
    )
    _write_json(
        pack_dir / "shop_items.json",
        [
            {
                "item_id": "snack",
                "name": "Snack",
                "category": "food",
                "icon": "item_icons/snack.png",
                "price": 1,
                "effects": {"mood": 1},
            }
        ],
    )
    return pack_dir


def test_validate_character_pack_tool_reports_complete_live2d_pack(tmp_path):
    pack_dir = _write_live2d_pack(tmp_path)

    result = subprocess.run(
        [sys.executable, str(TOOL), str(pack_dir)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["character_id"] == "xingxi_live2d"
    assert payload["errors"] == []


def test_validate_character_pack_tool_returns_nonzero_for_missing_live2d_model(tmp_path):
    pack_dir = _write_live2d_pack(tmp_path, with_model=False)

    result = subprocess.run(
        [sys.executable, str(TOOL), str(pack_dir)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert "character.json.renderer.model file not found: live2d/Xingxi.model3.json" in payload["errors"]
