from guanghe_companion.presentation_renderer import SpritePresentationAdapter


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
