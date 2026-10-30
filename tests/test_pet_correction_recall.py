import pytest

from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.mark.parametrize("mode", ["auto", "review"])
@pytest.mark.parametrize("species,correction", [("狗", "狗叫芝麻"), ("猫", "名字叫芝麻")])
def test_pet_correction_keeps_species_and_delivers_new_name_after_restart(tmp_path, mode, species, correction):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    memory = c.story_runtime.memory
    key = memory.propose_explicit_user_memory(f"请记住：我的{species}叫豆沙。", now=0)
    old = memory.confirm_candidate(key, now=0)
    extractor = ChatMemoryExtraction(memory)
    text = f"我说错了，{correction}。"
    envelope = extractor.prepare(text, now=0, mode=mode, generation=c.host_context_generation)
    proposal = MemoryProposal("correct", text, "芝麻", "pet", "宠物", (old.memory_id,), "explicit", "personal")
    extractor.apply(envelope, (proposal,), now=0, mode=mode, generation=c.host_context_generation)
    if mode == "review":
        memory.confirm_candidate(next(iter(memory.pending_candidates)), now=0)
    c.close()
    restarted = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=True)
    try:
        current = [m for m in restarted.story_runtime.memory.store.load_memories() if not m.deleted]
        assert len(current) == 1 and species in current[0].summary and "芝麻" in current[0].summary
        assert "豆沙" not in current[0].summary
        restarted._current_player_message = f"我家小{species}叫什么？这次别被我前面说错的名字带跑了。"
        context = restarted.get_expression_context()
        prompt = restarted.ai_expressor.build_prompt(ExpressionRequest.from_snapshot(restarted.get_typed_snapshot(), context=context))
        assert "芝麻" in prompt and "豆沙" not in prompt
        restarted.memory_album_controller.forget(current[0].memory_id, now=int(restarted.now))
        context = restarted.get_expression_context()
        forgotten_prompt = restarted.ai_expressor.build_prompt(ExpressionRequest.from_snapshot(restarted.get_typed_snapshot(), context=context))
        assert "芝麻" not in forgotten_prompt and "豆沙" not in forgotten_prompt
    finally:
        restarted.close()
