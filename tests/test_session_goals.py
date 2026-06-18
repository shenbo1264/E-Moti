from guanghe_companion.session_goals import SessionGoalTracker


def test_session_goal_tracker_completes_interaction_goal_and_advances():
    tracker = SessionGoalTracker()

    assert tracker.snapshot()["goal_id"] == "interact_twice"
    assert tracker.snapshot()["progress"] == 0
    assert tracker.snapshot()["target"] == 2

    first = tracker.record_event("action", action_id="touch")
    second = tracker.record_event("action", action_id="play")

    assert first.completed_goal_id == ""
    assert second.completed_goal_id == "interact_twice"
    assert second.reward == {"coins": 2, "exp": 1}
    assert tracker.snapshot()["goal_id"] == "rest_once"
    assert tracker.snapshot()["progress"] == 0


def test_session_goal_tracker_ignores_dialogue_events():
    tracker = SessionGoalTracker()

    result = tracker.record_event("dialogue", action_id="")

    assert result.completed_goal_id == ""
    assert tracker.snapshot()["goal_id"] == "interact_twice"
    assert tracker.snapshot()["progress"] == 0
