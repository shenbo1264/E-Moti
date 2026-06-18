from guanghe_companion.interaction_intents import (
    InteractionIntent,
    interaction_intents_from_payload_row,
)


def test_interaction_intents_accept_whitelisted_hint_as_readonly_payload():
    intents = interaction_intents_from_payload_row(
        {
            "type": "speech",
            "speech": "休息一下也可以。",
            "intent_hint": "offer_rest",
        }
    )

    assert intents == (
        InteractionIntent(intent_id="offer_rest", ttl_ms=5000, priority=50, source="llm"),
    )
    assert intents[0].to_dict() == {
        "id": "offer_rest",
        "ttl_ms": 5000,
        "priority": 50,
        "source": "llm",
    }


def test_interaction_intents_reject_unknown_or_unsafe_hints():
    assert interaction_intents_from_payload_row({"type": "speech", "speech": "x", "intent_hint": "write_save"}) == ()
    assert (
        interaction_intents_from_payload_row(
            {"type": "speech", "speech": "x", "intent_hint": "offer_rest\ncoins=999"}
        )
        == ()
    )
