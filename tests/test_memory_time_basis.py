"""Desktop logical seconds must never masquerade as real calendar dates."""
from datetime import datetime, timezone

from guanghe_companion.emotional_memory_service import EmotionalMemoryService


def fact(service, now):
    return service.remember(kind="用户事实", title="居住地", summary="用户住在西安。",
        source="user_chat", source_ids=("turn:1",), now=now,
        metadata={"fact_subject": "user:self", "fact_predicate": "residence",
                  "fact_value": "西安", "fact_slot": "residence"})


def test_logical_archive_keeps_current_facts_but_rejects_calendar_comparison(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet")
    entry = fact(service, 20)
    assert service.retrieve("我现在住在哪？", now=300).trace.selected_memory_ids == (entry.memory_id,)
    result = service.retrieve("2026年6月3日我住在哪？", now=300)
    assert result.trace.status == "insufficient"
    assert result.trace.retrieval_calls == 0
    assert not result.bundle.memories
    assert result.trace.intent_status[0]["reason"] == "unresolved_time_basis_or_date"


def test_unix_archive_calendar_window_and_invalid_date(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet", time_basis="unix")
    stamp = int(datetime(2026, 6, 3, 12, tzinfo=timezone.utc).timestamp())
    entry = fact(service, stamp)
    assert service.retrieve("6月3日我住在哪？", now=stamp+3*86400).trace.selected_memory_ids == (entry.memory_id,)
    result = service.retrieve("2026年2月30日我住在哪？", now=stamp+3*86400)
    assert result.trace.status == "insufficient"
    assert not result.bundle.memories
