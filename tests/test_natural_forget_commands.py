import pytest

from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.mark.parametrize("fact,command", [
    ("我的狗叫栗子。", "把我狗的事忘了吧。"),
    ("我在准备日语等级考试。", "日语等级考试那件事别记了。"),
    ("我每周参加陶艺课。", "陶艺课这件事不要再记了。"),
])
def test_topic_forget_retires_fact_and_prior_prompt(tmp_path, fact, command):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.memory_album_controller.remember_explicit(fact, now=0)
        c.submit_dialogue_request(DialogueRequest(command))
        assert c.last_chat_memory_result.status == "forgotten"
        assert not [m for m in c.story_runtime.memory.store.load_memories() if not m.deleted]
        assert fact not in str(c.get_expression_context())
    finally:
        c.close()


@pytest.mark.parametrize("text", ["不要忘记我的狗", "把我狗的事忘了是什么意思？", "假如把我狗的事忘了呢", "他说把我狗的事忘了吧",
    "小说里的狗叫栗子，把狗的事忘了吧", "可能把我狗的事忘了吧", "游戏里把我的狗忘了吧"])
def test_noncommands_do_not_revoke(tmp_path, text):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.memory_album_controller.remember_explicit("我的狗叫栗子。", now=0)
        c.submit_dialogue_request(DialogueRequest(text))
        assert any(not m.deleted for m in c.story_runtime.memory.store.load_memories())
    finally:
        c.close()


def test_unresolved_forget_is_clarification_even_without_model(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.submit_dialogue_request(DialogueRequest("那个事情别记了"))
        assert c.last_chat_memory_result.status == "clarify"
        assert "忘记了" not in c.last_feedback
    finally:
        c.close()


def test_empty_extraction_cannot_authorize_a_forget_reply(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        extractor = c.chat_memory_extraction
        envelope = extractor.prepare("那个事情别记了", now=0, mode="auto", generation=0)
        result = extractor.apply(envelope, (), now=0, mode="auto", generation=0)
        assert result.status == "clarify"
    finally:
        c.close()
