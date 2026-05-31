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


def test_dialogue_stream_parser_yields_typed_speech_events_from_chunked_json_array():
    from guanghe_companion.dialogue_parser import DialogueStreamParser

    parser = DialogueStreamParser(character_name="星汐")

    first = list(parser.feed('[{"type":"speech",'))
    second = list(parser.feed('"speech":"我在这里。","effect":"ATTENTION","motion_hint":"Raised"}]'))

    assert first == []
    assert len(second) == 1
    assert isinstance(second[0], CompanionEvent)
    assert second[0].event_type == "speech"
    assert second[0].character_name == "星汐"
    assert second[0].speech == "我在这里。"
    assert second[0].sprite == "1"
    assert second[0].effect == "ATTENTION"
    assert second[0].payload == {}
    assert parser.accumulated_text == (
        '[{"type":"speech","speech":"我在这里。","effect":"ATTENTION","motion_hint":"Raised"}]'
    )


def test_dialogue_stream_parser_rejects_state_mutation_fields():
    from guanghe_companion.dialogue_parser import DialogueStreamParser

    parser = DialogueStreamParser(character_name="星汐")

    events = list(parser.feed('[{"type":"speech","speech":"给你金币","effect":"ATTENTION","coins":999}]'))

    assert events == []
    assert parser.last_error == "unsafe_fields"


def test_dialogue_stream_parser_accepts_adjacent_shinsekai_style_objects():
    from guanghe_companion.dialogue_parser import DialogueStreamParser

    parser = DialogueStreamParser(character_name="星汐")

    events = list(
        parser.feed(
            '{"type":"speech","speech":"第一句。","effect":"ATTENTION"}'
            '{"type":"speech","speech":"第二句。","effect":"SWITCH"}'
        )
    )

    assert [event.speech for event in events] == ["第一句。", "第二句。"]
    assert [event.effect for event in events] == ["ATTENTION", "SWITCH"]
