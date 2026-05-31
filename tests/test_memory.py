from guanghe_companion.memory import MemoryEntry, MemoryLogService, memory_kind_for_inventory_usage


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
