from guanghe_companion.memory import (
    LongTermMemoryEntry,
    LongTermMemoryService,
    LongTermMemoryStore,
    MemoryEntry,
    MemoryLogService,
    memory_kind_for_inventory_usage,
)


def test_memory_entry_exports_legacy_log_row_with_optional_item_id():
    entry = MemoryEntry(
        at=35,
        kind="投喂",
        summary="投喂了 热牛奶：charge +12",
        motion="Eat",
        item_id="warm_milk",
    )

    assert entry.to_legacy_dict() == {
        "at": 35,
        "kind": "投喂",
        "summary": "投喂了 热牛奶：charge +12",
        "motion": "Eat",
        "item_id": "warm_milk",
    }


def test_memory_kind_for_inventory_usage_matches_existing_labels():
    assert memory_kind_for_inventory_usage("feed") == "投喂"
    assert memory_kind_for_inventory_usage("gift") == "赠礼"
    assert memory_kind_for_inventory_usage("use") == "使用"


def test_memory_entry_omits_item_id_when_absent():
    entry = MemoryEntry(at=40, kind="互动", summary="轻触：我听见你靠近了。", motion="TouchHead")

    assert entry.to_legacy_dict() == {
        "at": 40,
        "kind": "互动",
        "summary": "轻触：我听见你靠近了。",
        "motion": "TouchHead",
    }


def test_memory_log_service_appends_latest_first_and_caps_entries():
    memory_log = [{"at": index, "kind": "旧回忆", "summary": str(index), "motion": "Tick"} for index in range(12)]
    service = MemoryLogService(memory_log)

    service.append(at=99, kind="互动", summary="轻触：她靠近了一点", motion="TouchHead")

    assert memory_log[0] == {
        "at": 99,
        "kind": "互动",
        "summary": "轻触：她靠近了一点",
        "motion": "TouchHead",
    }
    assert len(memory_log) == 12
    assert memory_log[-1]["at"] == 10


def test_memory_log_service_appends_relationship_unlock_drafts_with_runtime_time():
    memory_log = []
    service = MemoryLogService(memory_log)

    service.append_drafts(
        at=125,
        drafts=[
            {"kind": "关系解锁", "summary": "第一次主动称呼解锁了。", "motion": "TouchHead"},
            {"kind": "关系解锁", "summary": "共同日常仪式解锁了。", "motion": "Study"},
        ],
    )

    assert memory_log == [
        {"at": 125, "kind": "关系解锁", "summary": "共同日常仪式解锁了。", "motion": "Study"},
        {"at": 125, "kind": "关系解锁", "summary": "第一次主动称呼解锁了。", "motion": "TouchHead"},
    ]


def test_long_term_memory_store_round_trips_entries(tmp_path):
    path = tmp_path / "long-term-memory.json"
    entry = LongTermMemoryEntry(
        key="relationship:unlock_first_nickname",
        category="relationship_unlock",
        summary="第一次主动称呼解锁了。",
        source="relationship_unlock",
        created_at=25,
        updated_at=25,
    )
    store = LongTermMemoryStore(path)

    store.save((entry,))

    assert store.load() == (entry,)


def test_long_term_memory_store_falls_back_to_empty_for_bad_json(tmp_path):
    path = tmp_path / "long-term-memory.json"
    path.write_text("{not json", encoding="utf-8")

    assert LongTermMemoryStore(path).load() == ()


def test_long_term_memory_service_replaces_by_key_without_duplication():
    old = LongTermMemoryEntry(
        key="relationship:unlock_first_nickname",
        category="relationship_unlock",
        summary="旧摘要",
        source="relationship_unlock",
        created_at=25,
        updated_at=25,
    )
    service = LongTermMemoryService(entries=(old,))

    updated = service.upsert(
        key="relationship:unlock_first_nickname",
        category="relationship_unlock",
        summary="第一次主动称呼解锁了。",
        source="relationship_unlock",
        now=40,
    )

    assert updated.created_at == 25
    assert updated.updated_at == 40
    assert service.entries == (updated,)
    assert service.summaries() == (
        {
            "category": "relationship_unlock",
            "summary": "第一次主动称呼解锁了。",
            "source": "relationship_unlock",
        },
    )


def test_long_term_memory_service_caps_newest_entries():
    entries = tuple(
        LongTermMemoryEntry(
            key=f"key:{index}",
            category="local_note",
            summary=f"summary {index}",
            source="local_api",
            created_at=index,
            updated_at=index,
        )
        for index in range(3)
    )
    service = LongTermMemoryService(entries=entries, max_entries=3)

    service.upsert(
        key="key:new",
        category="local_note",
        summary="new summary",
        source="local_api",
        now=10,
    )

    assert [entry.key for entry in service.entries] == ["key:new", "key:2", "key:1"]
