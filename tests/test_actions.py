from guanghe_companion.actions import CompanionAction, CompanionActionLayer, CompanionActionRequest
from guanghe_companion.engine import create_initial_state


def test_action_layer_builds_typed_actions_and_legacy_rows():
    state = create_initial_state(now=0)

    actions = CompanionActionLayer(state).available_actions()

    assert all(isinstance(action, CompanionAction) for action in actions)
    assert [action.action_id for action in actions] == ["touch", "soothe", "rest", "study", "play", "drag"]
    assert actions[0].label == "轻触"
    assert actions[0].motion == "TouchHead"
    assert actions[0].enabled is True
    assert actions[0].to_legacy_dict() == {
        "action_id": "touch",
        "label": "轻触",
        "motion": "TouchHead",
        "enabled": True,
    }


def test_action_layer_uses_state_to_disable_or_relabel_actions():
    state = create_initial_state(now=0)
    state.focus = 10
    state.resting = True

    actions = {action.action_id: action for action in CompanionActionLayer(state).available_actions()}

    assert actions["study"].enabled is False
    assert actions["rest"].label == "结束休息"


def test_action_request_preserves_action_id_and_source():
    request = CompanionActionRequest(action_id="drag", source="desktop_pet")

    assert request.action_id == "drag"
    assert request.source == "desktop_pet"
