from guanghe_companion.character_pack import load_default_character_pack, resolve_motion_caption


def test_load_default_character_pack_reads_original_oc_manifest():
    pack = load_default_character_pack()

    assert pack.character_id == "original_oc"
    assert pack.name == "光核伴生体"
    assert pack.default_mode == "Calm"
    assert "Glow" in pack.modes
    assert pack.motion_labels["TouchHead"] == "靠近回应"


def test_load_default_character_pack_reads_spritesheet_filename():
    pack = load_default_character_pack()

    assert pack.spritesheet == "spritesheet.png"


def test_resolve_motion_caption_uses_pack_motion_labels():
    pack = load_default_character_pack()

    caption = resolve_motion_caption(pack, motion="Study", mode="Calm", allowed=True)
    blocked = resolve_motion_caption(pack, motion="SwitchDown", mode="Overload", allowed=False)

    assert "共同学习" in caption
    assert "Overload" in blocked
