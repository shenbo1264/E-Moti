from guanghe_companion.controller import CompanionController
from guanghe_companion.events import CompanionEvent


def test_dialogue_request_generates_speech_without_mutating_growth_state(tmp_path):
    from guanghe_companion.dialogue import DialogueRequest

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    before = controller.get_typed_snapshot()

    snapshot = controller.submit_dialogue_request(
        DialogueRequest(text="今天想陪你待一会儿。"),
        include_ai_expression=False,
    )

    after = controller.get_typed_snapshot()
    assert after.stats == before.stats
    assert after.inventory == before.inventory
    assert after.relationship_stage == before.relationship_stage
    assert after.unlocks == before.unlocks
    assert after.memory_log == before.memory_log
    assert after.current_motion == "Default"
    assert all(isinstance(event, CompanionEvent) for event in controller.last_events)
    assert controller.last_events[0].event_type == "speech"
    assert snapshot["events"][0]["character_name"] == "星汐"
    assert "今天想陪你待一会儿" in snapshot["events"][0]["speech"]
    assert snapshot["mood"] == before.stats.mood
    assert snapshot["coins"] == before.stats.coins


def test_dialogue_request_trims_and_caps_user_text():
    from guanghe_companion.dialogue import DialogueRequest, MAX_DIALOGUE_INPUT_LENGTH

    request = DialogueRequest(text="  " + "星" * (MAX_DIALOGUE_INPUT_LENGTH + 20) + "  ")

    assert request.normalized_text() == "星" * MAX_DIALOGUE_INPUT_LENGTH

