from guanghe_companion import presentation_renderer
from guanghe_companion.presentation_renderer import PortraitPresentationAdapter, SpritePresentationAdapter


def test_sprite_presentation_adapter_uses_llm_visual_motion_without_mutating_snapshot():
    snapshot = {
        "motion": "Default",
        "visual_actions": [
            {
                "type": "motion",
                "id": "Raised",
                "ttl_ms": 1800,
                "priority": 60,
                "source": "llm",
            }
        ],
    }

    frame = SpritePresentationAdapter().frame_from_snapshot(snapshot)

    assert frame.backend == "sprite"
    assert frame.motion == "Raised"
    assert frame.visual_actions[0].action_id == "Raised"
    assert snapshot["motion"] == "Default"


def test_sprite_presentation_adapter_falls_back_to_snapshot_motion_when_no_motion_action():
    snapshot = {
        "motion": "Study",
        "visual_actions": [
            {
                "type": "expression",
                "id": "joy",
                "ttl_ms": 3000,
                "priority": 70,
                "source": "llm",
            }
        ],
    }

    frame = SpritePresentationAdapter().frame_from_snapshot(snapshot)

    assert frame.motion == "Study"


def test_sprite_presentation_adapter_uses_character_motion_map():
    snapshot = {
        "motion": "Default",
        "visual_actions": [
            {
                "type": "motion",
                "id": "Play",
                "ttl_ms": 1800,
                "priority": 60,
                "source": "llm",
            }
        ],
    }

    frame = SpritePresentationAdapter(motion_map={"Play": "TouchHead"}).frame_from_snapshot(snapshot)

    assert frame.motion == "TouchHead"


def test_live2d_web_presentation_adapter_maps_visual_actions_without_mutating_snapshot():
    snapshot = {
        "motion": "Default",
        "visual_actions": [
            {
                "type": "expression",
                "id": "excited",
                "ttl_ms": 3000,
                "priority": 70,
                "source": "llm",
            },
            {
                "type": "motion",
                "id": "Play",
                "ttl_ms": 1800,
                "priority": 60,
                "source": "llm",
            },
        ],
    }

    frame = presentation_renderer.Live2DWebPresentationAdapter(
        model_path="live2d/Xingxi.model3.json",
        expression_map={"excited": "F02"},
        motion_map={"Play": "TapBody"},
    ).frame_from_snapshot(snapshot)

    assert frame.backend == "live2d_web"
    assert frame.model_path == "live2d/Xingxi.model3.json"
    assert frame.motion == "TapBody"
    assert frame.live2d_actions == (
        {"type": "expression", "id": "excited", "mapped": "F02", "source": "llm"},
        {"type": "motion", "id": "Play", "mapped": "TapBody", "source": "llm"},
    )
    assert snapshot["motion"] == "Default"


def test_portrait_presentation_adapter_maps_visual_expression_without_mutating_snapshot():
    snapshot = {
        "motion": "Default",
        "visual_actions": [
            {
                "type": "expression",
                "id": "focused",
                "ttl_ms": 3000,
                "priority": 70,
                "source": "llm",
            }
        ],
    }

    frame = PortraitPresentationAdapter(
        portrait_manifest="portrait_manifest.json",
        expression_map={"focused": "thinking"},
    ).frame_from_snapshot(snapshot)

    assert frame.backend == "portrait"
    assert frame.portrait_manifest == "portrait_manifest.json"
    assert frame.portrait_id == "thinking"
    assert frame.motion == "Default"
    assert snapshot["motion"] == "Default"


def test_portrait_presentation_adapter_falls_back_to_neutral_when_expression_is_unknown():
    snapshot = {
        "motion": "Default",
        "visual_actions": [
            {
                "type": "expression",
                "id": "unknown",
                "ttl_ms": 3000,
                "priority": 70,
                "source": "llm",
            }
        ],
    }

    frame = PortraitPresentationAdapter(
        portrait_manifest="portrait_manifest.json",
        expression_map={"focused": "thinking"},
    ).frame_from_snapshot(snapshot)

    assert frame.portrait_id == "neutral"
