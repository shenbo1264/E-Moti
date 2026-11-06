from guanghe_companion.emotional_memory import EmotionalMemoryEntry
from guanghe_companion.memory_ledger_view_model import build_memory_ledger


def card(**changes):
    fields = dict(memory_id="event", character_id="xingxi_pixel_pet", owner_id="local_user",
        kind="日常", title="一段记录", summary="用户自己做的事情", source="journal",
        source_ids=("user-turn",), occurred_at=10, created_at=10, updated_at=10,
        metadata={"participants": ["user:self"], "event_status": "completed"})
    fields.update(changes)
    entry = EmotionalMemoryEntry(**fields).normalized()
    return next(c for section in build_memory_ledger((entry,), now=20) for c in section["cards"])


def test_personal_record_does_not_become_shared_experience():
    result = card()
    assert result["section"] != "episode"
    assert result["subject"] == "你"


def test_planned_game_event_is_not_presented_as_occurred():
    result = card(source="game_event", metadata={"event_status": "planned"})
    assert result["section"] == "plan"
    assert result["status_label"] == "计划中"


def test_executor_success_without_user_acceptance_is_explicit():
    result = card(source="trusted_executor", scope="task_experience",
                  metadata={"outcome": "succeeded", "user_accepted": False})
    assert result["section"] == "task"
    assert "未验收" in result["status_label"]
    accepted = card(source="trusted_executor", scope="task_experience",
                    metadata={"outcome": "succeeded", "user_accepted": True})
    assert accepted["status_label"] == "已验收"


def test_completed_grounded_shared_event_keeps_shared_presentation():
    result = card(source="game_event", kind="共同经历", summary="一起完成了一局游戏",
                  metadata={"event_status": "completed", "participants": ["user:self", "character:self"]})
    assert result["section"] == "episode" and result["subject"] == "你们"
