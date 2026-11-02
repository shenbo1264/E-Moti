"""Old document/SQL writers cannot bypass the dialogue revocation barrier."""
from dataclasses import replace
import json
import sqlite3

import pytest

from guanghe_companion.controller import HostDialogueStaleError
from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.emotional_memory import EmotionalMemoryEntry, EmotionalMemoryStore, MemoryChapter
from guanghe_companion.events import CompanionEvent
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def fact(key="drink", **extra):
    values = dict(memory_id=key, character_id="xingxi_pixel_pet", owner_id="local_user",
        kind="玩家希望被记住", title="饮料偏好", summary="用户喜欢喝紫苏冰饮",
        source="user_chat", occurred_at=10, created_at=10, updated_at=10,
        source_ids=("statement:" + key,), metadata={"fact_subject": "user:self",
            "fact_predicate": "饮料偏好", "fact_slot": "饮料偏好", "fact_domain": "饮料偏好",
            "fact_value": "紫苏冰饮", "speaker": "user", "scene": "companion_chat"})
    values.update(extra)
    return EmotionalMemoryEntry(**values)


def raw_write(store, operation, *, writer="document"):
    def mutate(document):
        row = document["entries"][0]
        if operation == "summary":
            row["summary"] = "用户喜欢喝青梅茶"
        elif operation == "metadata":
            row["metadata"]["fact_value"] = "青梅茶"
        elif operation == "deleted":
            row["deleted"] = True
        elif operation == "scope":
            row["scope"] = "work"
        elif operation == "remove":
            document["entries"] = []
        elif operation == "retire":
            document["retired_ids"] = [row["memory_id"]]
        elif operation == "expired":
            document["expired_revisions"] = [EmotionalMemoryEntry.from_dict(row).evidence_fingerprint()]
        else:
            raise AssertionError(operation)

    if writer == "document":
        with store._document() as document:
            mutate(document)
    else:
        with sqlite3.connect(store.state_path) as connection:
            document = json.loads(connection.execute("SELECT payload FROM memory_state WHERE id=1").fetchone()[0])
            mutate(document)
            connection.execute("UPDATE memory_state SET payload=? WHERE id=1", (json.dumps(document, ensure_ascii=False),))


@pytest.mark.parametrize("writer", ["document", "sql"])
@pytest.mark.parametrize("operation", ["summary", "metadata", "deleted", "scope", "remove", "retire", "expired"])
def test_raw_existing_source_change_advances_authority_and_projection_once(tmp_path, writer, operation):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    store.save_memories([fact()])
    before = store.current_index_state(now=20)
    raw_write(store, operation, writer=writer)
    after = store.current_index_state(now=20)
    assert after[2] == before[2] + 1
    assert after[1] > before[1]
    assert store.current_index_state(now=21) == after
    with sqlite3.connect(store.state_path) as connection:
        authority_epoch = connection.execute("SELECT json_extract(payload,'$.context_epoch') FROM memory_state WHERE id=1").fetchone()[0]
        projection = connection.execute("SELECT context_epoch,dirty FROM memory_index_meta WHERE id=1").fetchone()
    assert authority_epoch == projection[0] == after[2]
    assert projection[1] == 0


@pytest.mark.parametrize("writer", ["document", "sql"])
def test_raw_retraction_discards_inflight_model_answer_on_real_controller(tmp_path, writer):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        store = controller.story_runtime.memory.store
        store.upsert_memory(replace(fact(), character_id=controller.state.character_id, occurred_at=0, created_at=0, updated_at=0))
        ticket = controller.prepare_host_dialogue(DialogueRequest("我喜欢喝什么"))
        assert "紫苏冰饮" in ticket.expressor.build_prompt(ticket.expression_request)
        raw_write(store, "deleted", writer=writer)
        events = [CompanionEvent("speech", controller.state.character_name, "你喜欢紫苏冰饮。").to_legacy_dict()]
        with pytest.raises(HostDialogueStaleError):
            controller.complete_host_dialogue(ticket, events)
        assert not controller.dialogue_history
        assert "紫苏冰饮" not in json.dumps(controller.get_snapshot()["events"], ensure_ascii=False)
    finally:
        controller.close()


@pytest.mark.parametrize("writer", ["document", "sql"])
def test_raw_retraction_fences_existing_dialogue_history_and_old_feedback(tmp_path, writer):
    controller = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        store = controller.story_runtime.memory.store
        store.upsert_memory(replace(fact(), character_id=controller.state.character_id, occurred_at=0, created_at=0, updated_at=0))
        ticket = controller.prepare_host_dialogue(DialogueRequest("我喜欢喝什么"))
        events = [CompanionEvent("speech", controller.state.character_name, "你喜欢紫苏冰饮。").to_legacy_dict()]
        controller.complete_host_dialogue(ticket, events)
        assert any("紫苏冰饮" in entry.text for entry in controller.dialogue_history)
        raw_write(store, "remove", writer=writer)
        fresh = controller.prepare_host_dialogue(DialogueRequest("我喜欢喝什么"))
        assert "紫苏冰饮" not in fresh.expressor.build_prompt(fresh.expression_request)
        assert fresh.expression_request.recent_dialogue == ()
        controller.complete_host_dialogue(fresh)
        # The user can still inspect the archive; it is not inference context.
        assert any("紫苏冰饮" in entry.text for entry in controller.dialogue_history)
    finally:
        controller.close()


def test_dirty_sql_is_reconciled_before_legacy_epoch_read_or_expected_epoch_write(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    store.save_memories([fact()])
    epoch = store.context_epoch
    raw_write(store, "summary", writer="sql")
    assert store.context_epoch == epoch + 1
    raw_write(store, "metadata", writer="sql")
    with pytest.raises(ValueError, match="stale"):
        store.upsert_memory(fact("new"), expected_epoch=epoch + 1)
    # Rejecting the new write must not hide the pending raw source change.
    assert store.current_context_epoch(now=20) == epoch + 2
    assert all(row.memory_id != "new" for row in store.load_memories())


def test_normal_correction_and_expiry_are_not_double_incremented(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    original = fact(valid_until=30)
    store.save_memories([original])
    epoch = store.current_context_epoch(now=20)
    store.update_memory(replace(original, summary="用户喜欢喝青梅茶"))
    assert store.current_context_epoch(now=20) == epoch + 1
    store.expire_memories_indexed(now=30)
    assert store.current_context_epoch(now=30) == epoch + 2
    store.expire_memories_indexed(now=31)
    assert store.current_context_epoch(now=31) == epoch + 2


def test_new_facts_access_and_source_free_profile_changes_do_not_revoke(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    store.save_memories([fact()])
    epoch = store.current_context_epoch(now=20)
    store.upsert_memory(fact("new"))
    with store._document() as document:
        document["entries"].append(fact("new_raw").to_dict())
        document["profile"]["boundaries"] = ["尊重安静时间"]
    store.touch_memories(("drink",), now=21)
    with store._document() as document:
        document["entries"][0]["access_count"] += 1
    snapshot = store.read_indexed_snapshot(now=22)
    assert store.finalize_indexed_recall(snapshot.entries, expected_epoch=epoch, now=23)
    assert store.current_context_epoch(now=23) == epoch


def test_raw_epoch_cannot_move_backwards(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    store.save_memories([fact()])
    store.update_memory(replace(fact(), summary="用户喜欢喝青梅茶"))
    epoch = store.current_context_epoch(now=20)
    with store._document() as document:
        document["context_epoch"] = 0
    assert store.current_context_epoch(now=20) == epoch


def test_source_grounded_chapter_write_does_not_revoke_the_dialogue_epoch(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    original = fact()
    store.save_memories([original])
    before = store.current_index_state(now=20)
    chapter = MemoryChapter("stage", store.character_id, "阶段回忆", original.summary,
        (original.memory_id,), 20, source_fingerprints={original.memory_id: original.evidence_fingerprint()})
    store.upsert_chapter(chapter, expected_epoch=before[2])
    assert store.current_context_epoch(now=20) == before[2]
    assert store.read_indexed_snapshot(now=20).chapters


def test_failed_raw_transaction_does_not_revoke_or_change_source(tmp_path):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    store.save_memories([fact()])
    before = store.current_index_state(now=20)
    with pytest.raises(RuntimeError, match="abort"):
        with store._document() as document:
            document["entries"][0]["summary"] = "未提交的修订"
            raise RuntimeError("abort")
    assert store.current_index_state(now=20) == before
    assert store.load_memories()[0].summary == fact().summary
