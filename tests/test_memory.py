from guanghe_companion.memory import MemoryEntry, memory_kind_for_inventory_usage


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
