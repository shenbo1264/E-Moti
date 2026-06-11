from guanghe_companion.visual_actions import (
    VisualAction,
    clean_speech_and_visual_actions,
    pixel_motion_override,
    sprite_motion_override,
    visual_actions_from_payload_row,
)


def test_visual_actions_extract_open_llm_vtuber_style_tag_and_strip_tts_speech():
    speech, actions = clean_speech_and_visual_actions("[joy] 我在听。", motion_hint="")

    assert speech == "我在听。"
    assert actions == (
        VisualAction(action_type="expression", action_id="joy", ttl_ms=3000, priority=70, source="llm"),
        VisualAction(action_type="motion", action_id="TouchHead", ttl_ms=1800, priority=60, source="llm"),
    )


def test_visual_actions_accept_whitelisted_motion_hint_without_state_mutation_payload():
    actions = visual_actions_from_payload_row(
        {"type": "speech", "speech": "我会靠近一点。", "effect": "ATTENTION", "motion_hint": "Raised"}
    )

    assert actions == (
        VisualAction(action_type="motion", action_id="Raised", ttl_ms=1800, priority=60, source="llm"),
    )


def test_visual_actions_reject_unknown_tags_and_motion_hints():
    speech, actions = clean_speech_and_visual_actions("[rewrite_save] 保持原样。", motion_hint="DeleteInventory")

    assert speech == "保持原样。"
    assert actions == ()


def test_sprite_motion_override_uses_first_motion_action_only():
    actions = (
        VisualAction(action_type="expression", action_id="joy", ttl_ms=3000, priority=70, source="llm"),
        VisualAction(action_type="motion", action_id="Study", ttl_ms=1800, priority=60, source="llm"),
    )

    assert sprite_motion_override(actions) == "Study"
    assert sprite_motion_override(actions[:1]) is None


def test_pixel_motion_override_maps_expression_to_sprite_motion_family():
    actions = (
        VisualAction(action_type="expression", action_id="focused", ttl_ms=3000, priority=70, source="llm"),
    )

    assert pixel_motion_override(actions) == "Study"


def test_pixel_motion_override_prefers_explicit_motion_over_expression():
    actions = (
        VisualAction(action_type="expression", action_id="sleepy", ttl_ms=3000, priority=70, source="llm"),
        VisualAction(action_type="motion", action_id="Raised", ttl_ms=1800, priority=60, source="llm"),
    )

    assert pixel_motion_override(actions) == "Raised"


def test_visual_actions_accept_pixel_pet_expression_tags_without_new_state_control():
    speech, actions = clean_speech_and_visual_actions("[goofy] 嗯？我刚刚好像发呆了。", motion_hint="")

    assert speech == "嗯？我刚刚好像发呆了。"
    assert actions == (
        VisualAction(action_type="expression", action_id="goofy", ttl_ms=3000, priority=70, source="llm"),
        VisualAction(action_type="motion", action_id="Play", ttl_ms=1800, priority=60, source="llm"),
    )
