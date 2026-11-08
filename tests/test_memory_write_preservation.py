from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory import EmotionalMemoryEntry, EmotionalMemoryStore, _clean_text


@pytest.mark.parametrize("action", ["correct", "forget"])
def test_lifecycle_write_preserves_unrelated_raw_extensions(tmp_path, action):
    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    target = EmotionalMemoryEntry(memory_id="target", character_id=store.character_id,
        owner_id=store.owner_id, kind="用户自述", title="偏好", summary="用户喜欢青茶", source="user_chat",
        occurred_at=0, created_at=0, updated_at=0)
    unrelated = replace(target, memory_id="unrelated", summary="用户喜欢现代诗")
    store.save_memories((target, unrelated))
    with store._document() as document:
        row = next(row for row in document["entries"] if row["memory_id"] == "unrelated")
        row["future_extension"] = {"source_span": [7, 19], "version": 5}
        row["summary"] = "用户喜欢现代诗\t并阅读译本"
        expected = dict(row)
    if action == "correct":
        store.replace_memory("target", replace(target, memory_id="replacement", summary="用户喜欢红茶"), now=1)
    else:
        store.forget_memory("target", now=1)
    with store._document() as document:
        actual = next(row for row in document["entries"] if row["memory_id"] == "unrelated")
        assert actual == expected
        assert "target" in document["retired_ids"]
        assert document["context_epoch"] > 0


@pytest.mark.parametrize("text,limit,expected", [
    ("\x00甲\x1f乙\x7f丙", 20, "甲 乙 丙"),
    ("\u3000甲\t\r\n乙\u00a0丙  ", 20, "甲 乙 丙"),
    (" \U0001f642甲  乙 ", 3, "🙂甲 "),
    (None, 20, ""),
])
def test_text_normalization_keeps_existing_control_and_length_contract(text, limit, expected):
    assert _clean_text(text, limit) == expected


def test_correction_retains_ordinary_origin_but_rejects_purged_origin(tmp_path):
    from guanghe_companion.memory_lifecycle import purge_memory

    store = EmotionalMemoryStore(tmp_path, "xingxi_pixel_pet")
    entry = EmotionalMemoryEntry(memory_id="first", character_id=store.character_id,
        owner_id=store.owner_id, kind="用户自述", title="偏好", summary="用户喜欢青茶", source="user_chat",
        source_ids=("shared-source",), occurred_at=0, created_at=0, updated_at=0)
    store.upsert_memory(entry)
    corrected = store.replace_memory("first", replace(entry, memory_id="second"), now=1)
    store.replace_memory("second", replace(corrected, memory_id="third"), now=2)
    unrelated = replace(entry, memory_id="unrelated", source_ids=("other-source",))
    store.upsert_memory(unrelated)
    purge_memory(store, "third", now=3)
    assert store.is_retired_origin(entry=entry)
    with pytest.raises(ValueError, match="revoked"):
        store.replace_memory("unrelated", replace(entry, memory_id="replayed"), now=4)
