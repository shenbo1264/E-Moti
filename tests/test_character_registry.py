import json

from PIL import Image

from guanghe_companion.character_registry import CharacterRegistry, validate_character_pack_dir


REQUIRED_LIVE2D_EXPRESSION_MAP = {
    "calm": "F01",
    "excited": "F02",
    "surprised": "F03",
    "sleepy": "F05",
    "sadness": "F04",
    "focused": "F06",
}
REQUIRED_LIVE2D_MOTION_MAP = {
    "Default": "Idle",
    "Play": "TapBody",
    "Raised": "TapBody",
    "TouchHead": "TapHead",
    "Sleep": "Sleep",
}
REQUIRED_PORTRAIT_EXPRESSIONS = ("neutral", "smile", "thinking", "surprised", "sad", "sleepy")


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_minimal_pack(
    root,
    character_id="custom_character",
    *,
    icon_path="item_icons/snack.png",
    spritesheet="spritesheet.png",
    sheet_columns=8,
    default_frame_count=1,
):
    pack_dir = root / character_id
    (pack_dir / "item_icons").mkdir(parents=True)
    (pack_dir / "preview").mkdir()
    Image.new("RGBA", (sheet_columns * 192, 1872), (0, 0, 0, 0)).save(pack_dir / "spritesheet.png")
    Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(pack_dir / "item_icons" / "snack.png")
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(pack_dir / "preview" / "contact-sheet.png")
    _write_json(
        pack_dir / "character.json",
        {
            "character_id": character_id,
            "name": "澄光",
            "title": "桌面回声同伴",
            "description": "一个原创桌面伴侣。",
            "spritesheet": spritesheet,
            "motion_manifest": "motion_manifest.json",
            "default_mode": "Calm",
            "modes": ["Calm"],
            "mode_descriptions": {"Calm": "安静回应。"},
            "motion_labels": {"Default": "待机"},
        },
    )
    _write_json(
        pack_dir / "dialogue_style.json",
        {
            "tone": "安静、清晰",
            "keywords": ["回声", "桌面"],
            "fallback_style": "短句回应",
        },
    )
    _write_json(
        pack_dir / "motion_manifest.json",
        {
            "sheet_columns": sheet_columns,
            "sheet_rows": 9,
            "frame_width": 192,
            "frame_height": 208,
            "motions": {"Default": {"row": 0, "frame_count": default_frame_count, "fps": 4}},
        },
    )
    _write_json(
        pack_dir / "shop_items.json",
        [
            {
                "item_id": "snack",
                "name": "小点心",
                "category": "food",
                "icon": icon_path,
                "price": 1,
                "effects": {"mood": 1},
            }
        ],
    )
    return pack_dir


def _add_portrait_renderer(
    pack_dir,
    *,
    manifest_path="portrait_manifest.json",
    expressions=None,
    fallback_expression="neutral",
    image_mode="RGBA",
    image_size=(512, 768),
):
    (pack_dir / "portraits").mkdir(exist_ok=True)
    expression_map = {
        expression: f"portraits/{expression}.png"
        for expression in REQUIRED_PORTRAIT_EXPRESSIONS
    }
    if expressions is not None:
        expression_map = expressions
    for expression, relative_path in expression_map.items():
        paths = relative_path.values() if isinstance(relative_path, dict) else (relative_path,)
        for item_path in paths:
            path = pack_dir / item_path
            if item_path.startswith("portraits/"):
                path.parent.mkdir(exist_ok=True)
                Image.new(image_mode, image_size, (0, 0, 0, 0) if image_mode == "RGBA" else (0, 0, 0)).save(path)
    _write_json(
        pack_dir / manifest_path,
        {
            "version": 1,
            "fallback_expression": fallback_expression,
            "anchor": "bottom_center",
            "default_scale": 1.0,
            "expressions": expression_map,
        },
    )
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "portrait",
        "portrait_manifest": manifest_path,
        "expression_map": {
            "calm": "neutral",
            "joy": "smile",
            "excited": "smile",
            "focused": "thinking",
            "surprised": "surprised",
            "sadness": "sad",
            "sleepy": "sleepy",
        },
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_character_registry_lists_valid_packs_and_excludes_invalid_ones(tmp_path):
    _write_minimal_pack(tmp_path, "custom_character")
    invalid_dir = tmp_path / "broken_pack"
    invalid_dir.mkdir()
    _write_json(invalid_dir / "character.json", {"character_id": "broken_pack"})

    registry = CharacterRegistry(builtin_root=tmp_path)

    assert [pack.character_id for pack in registry.list_available_packs()] == ["custom_character"]
    assert registry.get_available_pack("custom_character").name == "澄光"
    assert registry.get_available_pack("custom_character").source == "builtin"

    reports = {report.character_id: report for report in registry.validate_all()}
    assert reports["custom_character"].ok
    assert not reports["broken_pack"].ok
    assert any("missing required file" in error for error in reports["broken_pack"].errors)


def test_character_registry_summary_reports_distribution_metadata_files(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path, "custom_character")
    (pack_dir / "portrait_assets_provenance.md").write_text("generated asset note", encoding="utf-8")
    (pack_dir / "LICENSE.md").write_text("pack license", encoding="utf-8")

    registry = CharacterRegistry(builtin_root=tmp_path)

    summary = registry.get_available_pack("custom_character")
    assert [path.name for path in summary.provenance_paths] == ["portrait_assets_provenance.md"]
    assert [path.name for path in summary.license_paths] == ["LICENSE.md"]


def test_validate_character_pack_rejects_icon_paths_outside_pack(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path, icon_path="../outside.png")

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("must stay inside item_icons" in error for error in report.errors)


def test_validate_character_pack_rejects_spritesheet_paths_outside_pack(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path, spritesheet="../outside.png")

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("spritesheet path must be a safe relative filename" in error for error in report.errors)


def test_validate_character_pack_accepts_manifest_declared_wide_sheet(tmp_path):
    pack_dir = _write_minimal_pack(
        tmp_path,
        sheet_columns=15,
        default_frame_count=15,
    )

    report = validate_character_pack_dir(pack_dir)

    assert report.ok


def test_validate_character_pack_rejects_invalid_renderer_mapping(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "sprite",
        "motion_map": {"Play": "../outside"},
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("character.json.renderer.motion_map.Play must be a safe renderer id" in error for error in report.errors)


def test_validate_character_pack_rejects_live2d_model_paths_outside_pack(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "live2d_web",
        "model": "../outside.model3.json",
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("character.json.renderer.model must be a safe relative model3 path" in error for error in report.errors)


def test_validate_character_pack_rejects_missing_live2d_model_file(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "live2d_web",
        "model": "live2d/Xingxi.model3.json",
        "expression_map": REQUIRED_LIVE2D_EXPRESSION_MAP,
        "motion_map": REQUIRED_LIVE2D_MOTION_MAP,
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("character.json.renderer.model file not found: live2d/Xingxi.model3.json" in error for error in report.errors)


def test_validate_character_pack_requires_live2d_expression_and_motion_coverage(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    live2d_dir = pack_dir / "live2d"
    live2d_dir.mkdir()
    (live2d_dir / "Xingxi.model3.json").write_text("{}", encoding="utf-8")
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "live2d_web",
        "model": "live2d/Xingxi.model3.json",
        "expression_map": {"calm": "F01"},
        "motion_map": {"Default": "Idle"},
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("character.json.renderer.expression_map missing required Live2D action: excited" in error for error in report.errors)
    assert any("character.json.renderer.motion_map missing required Live2D action: Play" in error for error in report.errors)


def test_validate_character_pack_accepts_complete_live2d_renderer_assets(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    live2d_dir = pack_dir / "live2d"
    live2d_dir.mkdir()
    (live2d_dir / "Xingxi.model3.json").write_text("{}", encoding="utf-8")
    character_path = pack_dir / "character.json"
    payload = json.loads(character_path.read_text(encoding="utf-8"))
    payload["renderer"] = {
        "backend": "live2d_web",
        "model": "live2d/Xingxi.model3.json",
        "expression_map": REQUIRED_LIVE2D_EXPRESSION_MAP,
        "motion_map": REQUIRED_LIVE2D_MOTION_MAP,
    }
    character_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = validate_character_pack_dir(pack_dir)

    assert report.ok


def test_validate_character_pack_accepts_complete_portrait_renderer_assets(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    _add_portrait_renderer(pack_dir)

    report = validate_character_pack_dir(pack_dir)

    assert report.ok


def test_validate_character_pack_rejects_missing_portrait_manifest(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    _add_portrait_renderer(pack_dir)
    (pack_dir / "portrait_manifest.json").unlink()

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("portrait manifest not found: portrait_manifest.json" in error for error in report.errors)


def test_validate_character_pack_rejects_portrait_path_outside_portraits(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    expressions = {
        expression: f"portraits/{expression}.png"
        for expression in REQUIRED_PORTRAIT_EXPRESSIONS
    }
    expressions["neutral"] = "../outside.png"
    _add_portrait_renderer(pack_dir, expressions=expressions)

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("portrait_manifest.expressions.neutral path must stay inside portraits" in error for error in report.errors)


def test_validate_character_pack_requires_portrait_expression_coverage(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    expressions = {
        expression: f"portraits/{expression}.png"
        for expression in REQUIRED_PORTRAIT_EXPRESSIONS
        if expression != "sleepy"
    }
    _add_portrait_renderer(pack_dir, expressions=expressions)

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("portrait_manifest.expressions missing required portrait expression: sleepy" in error for error in report.errors)


def test_validate_character_pack_rejects_portrait_fallback_not_in_manifest(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    _add_portrait_renderer(pack_dir, fallback_expression="missing")

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("portrait_manifest.fallback_expression must reference an expression" in error for error in report.errors)


def test_validate_character_pack_rejects_non_rgba_portrait_image(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    _add_portrait_renderer(pack_dir, image_mode="RGB")

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("portrait image mode must be RGBA" in error for error in report.errors)


def test_validate_character_pack_rejects_oversized_portrait_image(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    _add_portrait_renderer(pack_dir, image_size=(4097, 32))

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("portrait image too large" in error for error in report.errors)


def test_validate_character_pack_accepts_structured_portrait_blink_frames(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    expressions = {
        expression: f"portraits/{expression}.png"
        for expression in REQUIRED_PORTRAIT_EXPRESSIONS
    }
    expressions["neutral"] = {
        "open": "portraits/neutral_open.png",
        "blink_half": "portraits/neutral_half.png",
        "blink_closed": "portraits/neutral_closed.png",
    }
    _add_portrait_renderer(pack_dir, expressions=expressions)

    report = validate_character_pack_dir(pack_dir)

    assert report.ok


def test_validate_character_pack_accepts_nested_portrait_asset_subdirectory(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    expressions = {
        expression: {
            "open": f"portraits/vn/{expression}_open.png",
            "blink_half": f"portraits/vn/{expression}_half.png",
            "blink_closed": f"portraits/vn/{expression}_closed.png",
        }
        for expression in REQUIRED_PORTRAIT_EXPRESSIONS
    }
    _add_portrait_renderer(pack_dir, expressions=expressions)

    report = validate_character_pack_dir(pack_dir)

    assert report.ok


def test_validate_character_pack_rejects_unsafe_structured_portrait_blink_path(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    expressions = {
        expression: f"portraits/{expression}.png"
        for expression in REQUIRED_PORTRAIT_EXPRESSIONS
    }
    expressions["neutral"] = {
        "open": "portraits/neutral_open.png",
        "blink_half": "../neutral_half.png",
        "blink_closed": "portraits/neutral_closed.png",
    }
    _add_portrait_renderer(pack_dir, expressions=expressions)

    report = validate_character_pack_dir(pack_dir)

    assert not report.ok
    assert any("portrait_manifest.expressions.neutral.blink_half path must stay inside portraits" in error for error in report.errors)


def test_character_registry_can_merge_builtin_and_user_packs(tmp_path):
    builtin_root = tmp_path / "builtin"
    user_root = tmp_path / "user"
    _write_minimal_pack(builtin_root, "builtin_character")
    _write_minimal_pack(user_root, "user_character")

    registry = CharacterRegistry(builtin_root=builtin_root, user_root=user_root)

    packs = {pack.character_id: pack for pack in registry.list_available_packs()}
    assert packs["builtin_character"].source == "builtin"
    assert packs["user_character"].source == "user"
    assert packs["user_character"].preview_path.name == "contact-sheet.png"
