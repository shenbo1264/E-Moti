import pytest

from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def active(controller):
    return [m for m in controller.story_runtime.memory.store.load_memories() if not m.deleted]


def say(controller, text):
    return controller.submit_dialogue_request(DialogueRequest(text))


def test_ordinary_preference_restart_correct_forget(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, "我更喜欢乌龙茶，不太喜欢太甜的饮料。")
        rows = active(c)
        assert len(rows) == 2
        assert all(m.source_ids and m.metadata["speaker"] == "user" for m in rows)
        assert all(not m.user_confirmed for m in rows)
        assert c.story_runtime.memory.valid_profile(now=0).stable_preferences
    finally:
        c.close()
    c = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        say(c, "刚才说错了，我喜欢的是红茶。")
        assert not any("乌龙茶" in m.summary for m in active(c))
        assert any("红茶" in m.summary for m in active(c))
        say(c, "别再记我的饮料偏好了。")
        assert not active(c)
        assert not c.story_runtime.memory.valid_profile(now=0).stable_preferences
        context = str(c.get_expression_context())
        assert "乌龙茶" not in context and "红茶" not in context
    finally:
        c.close()


@pytest.mark.parametrize("text", [
    "小说主角喜欢咖啡", "假如我改喝咖啡呢", "朋友住在上海", "游戏里我住在城堡",
    "我今天想喝咖啡", "我可能喜欢咖啡", "我不确定自己喜欢什么", "我喜欢什么？",
    "他说我喜欢咖啡", "我喜欢他说的那个人", "我喜欢咖啡吗", "我喜欢咖啡还是红茶呢",
])
def test_ambiguous_or_nonreal_chat_is_not_a_fact(tmp_path, text):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, text)
        assert not active(c)
    finally:
        c.close()


def test_memory_mode_is_persisted_and_conflict_needs_review(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.set_chat_memory_mode("off")
        say(c, "我喜欢乌龙茶")
        assert not active(c)
        c.set_chat_memory_mode("review")
        say(c, "我喜欢乌龙茶")
        assert not active(c)
        pending = c.story_runtime.memory.pending_candidates
        assert len(pending) == 1
        c.memory_album_controller.confirm_pending(next(iter(pending)), now=0)
        c.set_chat_memory_mode("auto")
        say(c, "我喜欢红茶")
        assert len(active(c)) == 1
        assert len(c.story_runtime.memory.pending_candidates) == 1
    finally:
        c.close()


def test_clear_preference_change_replaces_old_fact(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, "我喜欢乌龙茶")
        say(c, "我现在改喝红茶了")
        assert len(active(c)) == 1
        assert "红茶" in active(c)[0].summary
    finally:
        c.close()


def test_confirmed_conflict_refreshes_profile_and_provenance(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, "我喜欢乌龙茶")
        say(c, "我喜欢红茶")
        pending = next(iter(c.story_runtime.memory.pending_candidates))
        c.memory_album_controller.confirm_pending(pending, now=5)
        assert c.story_runtime.memory.valid_profile(now=5).stable_preferences == ("用户喜欢红茶",)
        details = c.memory_album_controller.source_details(active(c)[0].memory_id, now=5)
        assert details["provenance"]["original_quote"] == "我喜欢红茶"
    finally:
        c.close()


def test_named_forget_does_not_reintroduce_value_as_new_chat(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        say(c, "我喜欢乌龙茶")
        say(c, "忘记我喜欢乌龙茶这件事")
        assert "乌龙茶" not in str(c.get_expression_context())
    finally:
        c.close()


def test_album_forget_rebuilds_chapter_from_remaining_real_sources(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        for index in range(4):
            c.story_runtime.record_settled_events([{"event_type": "inventory", "event_id": f"gift:{index}",
                "payload": {"action": "gift", "item_id": f"gift-{index}",
                            "item_name": f"纪念礼物{index}", "first_time": True}}], now=index)
        c.now = 10
        removed = next(m for m in active(c) if "纪念礼物0" in m.summary)
        c.memory_album_controller.forget(removed.memory_id, now=10)
        chapters = c.story_runtime.memory.valid_chapters(now=10)
        assert chapters
        assert set(chapters[-1].source_memory_ids) == {m.memory_id for m in active(c)}
        assert all("纪念礼物0" not in chapter.summary for chapter in chapters)
    finally:
        c.close()
