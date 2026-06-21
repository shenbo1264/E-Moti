import json
from pathlib import Path

from PIL import Image

from guanghe_companion.character_pack import load_character_pack_from_dir, load_default_character_pack, resolve_motion_caption
from guanghe_companion.character_registry import validate_character_pack_dir
from guanghe_companion.engine import BUYABLE_ITEMS


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_default_character_pack_reads_xingxi_pixel_pet_manifest():
    pack = load_default_character_pack()

    assert pack.character_id == "xingxi_pixel_pet"
    assert pack.name == "星汐"
    assert pack.default_mode == "Calm"
    assert "Glow" in pack.modes
    assert pack.motion_labels["TouchHead"] == "招手回应"


def test_load_default_character_pack_reads_spritesheet_filename():
    pack = load_default_character_pack()

    assert pack.spritesheet == "spritesheet.png"
    assert pack.renderer.backend == "sprite"
    assert pack.renderer.motion_map["Play"] == "Play"
    assert pack.renderer.expression_map["joy"] == "TouchHead"


def test_bundled_xingxi_pixel_pet_pack_is_valid_sprite_candidate():
    pack_dir = REPO_ROOT / "assets" / "companion" / "xingxi_pixel_pet"

    report = validate_character_pack_dir(pack_dir)
    pack = load_character_pack_from_dir(pack_dir)

    assert report.ok is True
    assert pack.character_id == "xingxi_pixel_pet"
    assert pack.renderer.backend == "sprite"
    assert pack.renderer.expression_map["goofy"] == "Play"


def test_bundled_original_oc_pack_remains_valid_fallback():
    pack_dir = REPO_ROOT / "assets" / "companion" / "original_oc"

    report = validate_character_pack_dir(pack_dir)
    pack = load_character_pack_from_dir(pack_dir)

    assert report.ok is True
    assert pack.character_id == "original_oc"
    assert pack.renderer.backend == "portrait"


def test_load_character_pack_reads_live2d_renderer_model_path(tmp_path):
    pack_dir = tmp_path / "live2d_character"
    (pack_dir / "live2d").mkdir(parents=True)
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    (pack_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 1,
                "sheet_rows": 1,
                "frame_width": 16,
                "frame_height": 16,
                "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": "live2d_character",
                "name": "Live2D",
                "title": "Live2D companion",
                "description": "Live2D test pack",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Calm"},
                "motion_labels": {"Default": "Idle"},
                "renderer": {
                    "backend": "live2d_web",
                    "model": "live2d/Xingxi.model3.json",
                    "motion_map": {"Play": "TapBody"},
                    "expression_map": {"excited": "F02"},
                },
            }
        ),
        encoding="utf-8",
    )

    pack = load_character_pack_from_dir(pack_dir)

    assert pack.renderer.backend == "live2d_web"
    assert pack.renderer.model == "live2d/Xingxi.model3.json"
    assert pack.renderer.motion_map["Play"] == "TapBody"
    assert pack.renderer.expression_map["excited"] == "F02"


def test_load_character_pack_reads_portrait_renderer_manifest_path(tmp_path):
    pack_dir = tmp_path / "portrait_character"
    pack_dir.mkdir()
    Image.new("RGBA", (192, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    (pack_dir / "motion_manifest.json").write_text(
        json.dumps(
            {
                "sheet_columns": 1,
                "sheet_rows": 9,
                "frame_width": 192,
                "frame_height": 208,
                "motions": {"Default": {"row": 0, "frame_count": 1, "fps": 4}},
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "character.json").write_text(
        json.dumps(
            {
                "character_id": "portrait_character",
                "name": "Portrait",
                "title": "Portrait companion",
                "description": "Portrait test pack",
                "spritesheet": "spritesheet.png",
                "motion_manifest": "motion_manifest.json",
                "default_mode": "Calm",
                "modes": ["Calm"],
                "mode_descriptions": {"Calm": "Calm"},
                "motion_labels": {"Default": "Idle"},
                "renderer": {
                    "backend": "portrait",
                    "portrait_manifest": "portrait_manifest.json",
                    "expression_map": {"focused": "thinking"},
                },
            }
        ),
        encoding="utf-8",
    )

    pack = load_character_pack_from_dir(pack_dir)

    assert pack.renderer.backend == "portrait"
    assert pack.renderer.portrait_manifest == "portrait_manifest.json"
    assert pack.renderer.expression_map["focused"] == "thinking"


def test_load_default_character_pack_reads_relationship_badges_from_existing_item_icons():
    pack = load_default_character_pack()

    assert pack.relationship_decorations == (
        {
            "unlock_id": "unlock_first_nickname",
            "item_id": "star_hairpin",
            "label": "星形发夹",
            "icon": "item_icons/star_hairpin.png",
        },
        {
            "unlock_id": "unlock_shared_ritual",
            "item_id": "comet_ribbon",
            "label": "彗尾丝带",
            "icon": "item_icons/comet_ribbon.png",
        },
    )
    for decoration in pack.relationship_decorations:
        item = BUYABLE_ITEMS[decoration["item_id"]]
        assert decoration["icon"] == item.icon


def test_resolve_motion_caption_uses_pack_motion_labels():
    pack = load_default_character_pack()

    caption = resolve_motion_caption(pack, motion="Study", mode="Calm", allowed=True)
    blocked = resolve_motion_caption(pack, motion="SwitchDown", mode="Overload", allowed=False)

    assert "专注检查" in caption
    assert "Overload" in blocked
