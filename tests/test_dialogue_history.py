from pathlib import Path


def test_dialogue_history_store_round_trips_copy_clear_replay_and_revert(tmp_path):
    from guanghe_companion.dialogue_history import (
        DialogueHistoryStore,
        append_dialogue_exchange,
        format_dialogue_history_text,
        replay_latest_assistant,
        revert_latest_exchange,
    )

    store = DialogueHistoryStore(tmp_path / "dialogue-history.json")
    entries = append_dialogue_exchange(
        (),
        user_text="今天陪我一会儿",
        assistant_name="星汐",
        assistant_text="我听见了：今天陪我一会儿",
        effect="ATTENTION",
    )
    entries = append_dialogue_exchange(
        entries,
        user_text="再说一句",
        assistant_name="星汐",
        assistant_text="我还在这里。",
        effect="SWITCH",
    )

    store.save(entries)
    loaded = store.load()

    assert [entry.role for entry in loaded] == ["user", "assistant", "user", "assistant"]
    assert format_dialogue_history_text(loaded) == (
        "你：今天陪我一会儿\n"
        "星汐：我听见了：今天陪我一会儿\n"
        "你：再说一句\n"
        "星汐：我还在这里。"
    )
    assert replay_latest_assistant(loaded).text == "我还在这里。"

    reverted, replay_entry = revert_latest_exchange(loaded)

    assert [entry.text for entry in reverted] == ["今天陪我一会儿", "我听见了：今天陪我一会儿"]
    assert replay_entry.text == "我听见了：今天陪我一会儿"

    store.clear()

    assert store.load() == ()
    assert Path(store.path).exists()


def test_dialogue_history_store_ignores_invalid_or_unsafe_payloads(tmp_path):
    from guanghe_companion.dialogue_history import DialogueHistoryStore

    path = tmp_path / "dialogue-history.json"
    path.write_text('{"entries":[{"role":"assistant","speaker":"星汐","text":"bad\\nline"}]}', encoding="utf-8")

    assert DialogueHistoryStore(path).load() == ()

    path.write_text('{"entries":[{"role":"inventory","speaker":"系统","text":"coins +999"}]}', encoding="utf-8")

    assert DialogueHistoryStore(path).load() == ()
