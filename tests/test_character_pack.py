from guanghe_companion.character_pack import load_default_character_pack, resolve_motion_caption
from guanghe_companion.engine import BUYABLE_ITEMS


def test_load_default_character_pack_reads_original_oc_manifest():
    pack = load_default_character_pack()

    assert pack.character_id == "original_oc"
    assert pack.name == "星汐"
    assert pack.default_mode == "Calm"
    assert "Glow" in pack.modes
    assert pack.motion_labels["TouchHead"] == "靠近回应"


def test_load_default_character_pack_reads_spritesheet_filename():
    pack = load_default_character_pack()

    assert pack.spritesheet == "spritesheet.png"


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

    assert "共同学习" in caption
    assert "Overload" in blocked
