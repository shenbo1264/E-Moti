"""Public correction and spoken forgetting respect typed literal facts."""
import json

import pytest

from guanghe_companion.chat_memory import ChatMemory
from guanghe_companion.emotional_memory import CoreBondProfile, MemoryChapter
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_index import IndexedMemoryQuery


def service(tmp_path):
    return EmotionalMemoryService(root=tmp_path, character_id="test_character")


def metadata(value):
    return {"speaker": "user", "fact_subject": "user:self", "fact_predicate": "settings",
            "fact_slot": "settings", "fact_domain": "设备设置", "fact_value": value}


def remember(memory, value):
    return memory.remember(kind="用户事实", title="设备设置",
        summary="用户确认设备设置为 " + json.dumps(value, ensure_ascii=False, sort_keys=True),
        source="user_chat", now=10, source_ids=("statement:settings",), metadata=metadata(value))


@pytest.mark.parametrize("value", [{"mode": "静音", "count": 0, "enabled": False},
    [{"mode": "静音"}, {"fallback": None}], {"quoted": 'a"b', "path": r"C:\work"},
    ["静音", "深色"], 0, False, 7.5, None])
def test_explicit_typed_correction_keeps_value_types_and_literal_body(tmp_path, value):
    memory = service(tmp_path)
    old = remember(memory, "原设置")
    summary = "用户将设备设置更正为 " + json.dumps(value, ensure_ascii=False, sort_keys=True)
    new = memory.correct(old.memory_id, title="设备设置", summary=summary,
        now=20, metadata=metadata(value))
    assert new.metadata["fact_value"] == value
    assert type(new.metadata["fact_value"]) is type(value)
    assert new.summary == summary
    assert new.supersedes == old.memory_id
    assert old.memory_id not in {m.memory_id for m in memory.store.read_indexed_snapshot(now=21).entries}
    restarted = service(tmp_path)
    assert restarted.store.read_indexed_snapshot(now=21).entries[0].metadata["fact_value"] == value


@pytest.mark.parametrize("value, summary", [
    ({"mode": "静音", "unproved": "隐藏值"}, "用户将模式改为静音"),
    ({"count": 7}, "用户将数量更正为 17"),
    ({"count": 0}, "用户使用 M10 型号"),
    ({"enabled": False}, "用户说 falsehood 是一个英文单词"),
    ({"fallback": None}, "用户将备用设置保持原样"),
    ({"value": "尾部值"}, "正文" * 130 + " 尾部值"),
    ({"depth": {"a": {"b": {"c": {"d": "过深"}}}}}, "过深"),
])
def test_typed_correction_rejects_unproved_or_truncated_scalar_leaf_atomically(tmp_path, value, summary):
    memory = service(tmp_path)
    old = remember(memory, "原设置")
    before = memory.store.current_index_state(now=15)
    with pytest.raises(ValueError):
        memory.correct(old.memory_id, title="设备设置", summary=summary, now=20, metadata=metadata(value))
    assert memory.store.current_index_state(now=21) == before
    assert memory.store.read_indexed_snapshot(now=21).entries[0].memory_id == old.memory_id


@pytest.mark.parametrize("value", [{"mode": "静音"}, ["静音"], 7, 7.5, True])
def test_spoken_forget_does_not_crash_or_overdelete_non_string_values(tmp_path, value):
    memory = service(tmp_path)
    old = remember(memory, value)
    chat = ChatMemory(memory, tmp_path / "settings.json")
    result = chat.process("忘掉咖啡偏好", now=20)
    assert result.status == "clarify"
    assert [m.memory_id for m in memory.store.read_indexed_snapshot(now=20).entries] == [old.memory_id]
    result = chat.process("忘掉这条", now=21)
    assert result.status == "forgotten"
    assert not memory.store.read_indexed_snapshot(now=22).entries


def test_public_structured_correction_then_forget_revokes_old_and_derived_sources(tmp_path):
    memory = service(tmp_path)
    old = remember(memory, {"mode": "晨雾设置", "count": 1})
    refs = {old.memory_id: old.evidence_fingerprint()}
    memory.store.save_profile(CoreBondProfile(memory.store.character_id,
        stable_preferences=("设备设置",), evidence={"stable_preferences:设备设置": refs}))
    memory.store.save_chapters([MemoryChapter("settings-chapter", memory.store.character_id,
        "设置概览", old.summary, (old.memory_id,), 12, source_fingerprints=refs)])
    before = memory.store.read_indexed_snapshot(now=15)
    value = {"mode": "晚霞设置", "count": 0, "enabled": False}
    new = memory.correct(old.memory_id, title="设备设置",
        summary="用户改为晚霞设置，count=0，enabled=false", now=20, metadata=metadata(value))
    snapshot = memory.store.read_indexed_snapshot(now=21)
    assert snapshot.context_epoch == before.context_epoch + 1
    assert snapshot.entries[0].metadata["fact_value"] == value
    assert memory.store.finalize_indexed_recall(before.entries,
        expected_epoch=before.context_epoch, now=21) is None
    assert not snapshot.chapters and not snapshot.profile.stable_preferences
    assert not memory.store.read_indexed_snapshot(IndexedMemoryQuery(query="晨雾"), now=21).entries
    assert memory.store.read_indexed_snapshot(IndexedMemoryQuery(query="晚霞"), now=21).entries[0].memory_id == new.memory_id
    result = ChatMemory(memory, tmp_path / "settings.json").process("忘掉设备设置", now=22)
    assert result.status == "forgotten"
    assert not service(tmp_path).store.read_indexed_snapshot(now=23).entries


def test_legacy_repair_preserves_new_proved_typed_correction_on_rebuild(tmp_path):
    memory = service(tmp_path)
    old = remember(memory, "原设置")
    value = {"mode": "静音", "count": 0}
    new = memory.correct(old.memory_id, title="设备设置", summary="用户的设备设置是静音，count=0",
        now=20, metadata=metadata(value))
    # A copied/imported document can run the legacy upgrade again. It must not
    # reinterpret a newly supported, fully literal correction as an old typo.
    with memory.store._document() as document:
        document["migrations"].pop("semantic_metadata_fingerprint_v1", None)
    restarted = service(tmp_path)
    current = restarted.store.read_indexed_snapshot(now=21).entries[0]
    assert current.memory_id == new.memory_id
    assert current.metadata["fact_value"] == value
    assert current.evidence_fingerprint() == new.evidence_fingerprint()
