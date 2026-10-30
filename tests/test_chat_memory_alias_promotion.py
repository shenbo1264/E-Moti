import pytest

from guanghe_companion.dialogue import DialogueRequest
from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


def prompt(controller):
    context = controller.get_expression_context()
    return controller.ai_expressor.build_prompt(ExpressionRequest.from_snapshot(controller.get_typed_snapshot(), context=context))


@pytest.mark.parametrize("mode", ["auto", "review"])
def test_new_nickname_retires_old_profile_and_forget_cannot_restore_state(tmp_path, mode):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.set_player_alias("阿枫")
        c.set_chat_memory_mode(mode)
        c.submit_dialogue_request(DialogueRequest("请叫我小溪"))
        memory = c.story_runtime.memory
        if mode == "review":
            assert memory.valid_profile(now=int(c.now)).player_alias == "阿枫"
            key = next(iter(memory.pending_candidates))
            c.memory_album_controller.confirm_pending(key, now=int(c.now))
        assert memory.valid_profile(now=int(c.now)).player_alias == "小溪"
        assert "阿枫" not in prompt(c)
        assert "小溪" in prompt(c)
        entries = [m for m in memory.store.load_memories() if not m.deleted]
        assert len(entries) == 1 and entries[0].source == "user_chat"
        assert entries[0].user_confirmed == (mode == "review")
        c.memory_album_controller.forget(entries[0].memory_id, now=int(c.now))
        assert memory.valid_profile(now=int(c.now)).player_alias == ""
        assert "阿枫" not in prompt(c) and "小溪" not in prompt(c)
        assert c.state.player_alias == "阿枫"
    finally:
        c.close()


def test_real_name_does_not_override_nickname(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.set_player_alias("阿枫")
        c.submit_dialogue_request(DialogueRequest("我的名字是林澈"))
        assert c.story_runtime.memory.valid_profile(now=int(c.now)).player_alias == "阿枫"
    finally:
        c.close()


def test_semantic_nickname_uses_same_profile_authority(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        c.set_player_alias("阿枫")
        extractor = ChatMemoryExtraction(c.story_runtime.memory)
        text = "平时称呼我小溪就好"
        envelope = extractor.prepare(text, now=int(c.now), mode="auto", generation=c.host_context_generation)
        proposal = MemoryProposal("remember", text, "小溪", "name", "称呼", (), "explicit", "personal")
        result = extractor.apply(envelope, (proposal,), now=int(c.now), mode="auto", generation=c.host_context_generation)
        assert result.status == "saved"
        c._on_memory_invalidated()
        assert "阿枫" not in prompt(c) and "小溪" in prompt(c)
        assert c.story_runtime.memory.valid_profile(now=int(c.now)).player_alias == "小溪"
    finally:
        c.close()
