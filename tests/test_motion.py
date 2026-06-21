import json
from pathlib import Path

from PIL import Image
import guanghe_companion.character_pack as character_pack_module
import guanghe_companion.motion as motion_module
from guanghe_companion.motion import MotionAnimator, load_default_motion_catalog, load_motion_catalog


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_default_motion_catalog_reads_core_rows():
    catalog = load_default_motion_catalog()

    idle = catalog.resolve("Default")
    touch = catalog.resolve("TouchHead")

    assert catalog.sheet_columns == 8
    assert catalog.frame_width == 192
    assert catalog.frame_height == 208
    assert idle.row == 0
    assert idle.frame_count == 6
    assert touch.row == 3
    assert touch.frame_count == 4


def test_motion_catalog_uses_spritesheet_from_character_pack(tmp_path, monkeypatch):
    character_id = "custom_character"
    asset_dir = tmp_path / character_id
    asset_dir.mkdir()
    (asset_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": character_id,
                "name": "Custom",
                "title": "Custom Title",
                "description": "Custom character pack",
                "spritesheet": "custom.webp",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Quiet mode"},
                "motion_labels": {"Default": "Idle"},
            }
        ),
        encoding="utf-8",
    )
    (asset_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 1,
                "sheet_rows": 1,
                "frame_width": 16,
                "frame_height": 16,
                "motions": {
                    "Default": {
                        "row": 0,
                        "frame_count": 1,
                        "fps": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(character_pack_module, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(motion_module, "ASSETS_ROOT", tmp_path)
    catalog = load_motion_catalog(character_id)

    assert catalog.sheet_path.name == "custom.webp"


def test_motion_animator_cycles_frames_for_selected_motion():
    catalog = load_default_motion_catalog()
    animator = MotionAnimator(catalog)

    animator.set_motion("TouchHead")
    first = animator.current_frame_rect()
    second = animator.advance()
    third = animator.advance()

    assert first.x() == 0
    assert second.x() == 192
    assert third.x() == 384
    assert first.y() == second.y() == third.y() == 208 * 3


def test_motion_animator_falls_back_to_default_when_motion_missing():
    catalog = load_default_motion_catalog()
    animator = MotionAnimator(catalog)

    animator.set_motion("UnknownMotion")
    rect = animator.current_frame_rect()

    assert rect.y() == 0
    assert rect.width() == 192


def test_xingxi_pixel_pet_manifest_includes_approved_confused_shy_motion():
    pack_dir = REPO_ROOT / "assets" / "companion" / "xingxi_pixel_pet"
    manifest = json.loads((pack_dir / "motion_manifest.json").read_text(encoding="utf-8"))

    assert manifest["sheet_rows"] == 10
    assert manifest["motions"]["ConfusedShy"] == {"row": 9, "frame_count": 6, "fps": 5}

    with Image.open(pack_dir / "spritesheet.png") as image:
        assert image.mode == "RGBA"
        assert image.size == (
            manifest["sheet_columns"] * manifest["frame_width"],
            manifest["sheet_rows"] * manifest["frame_height"],
        )
