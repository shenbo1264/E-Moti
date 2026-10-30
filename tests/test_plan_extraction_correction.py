import pytest

from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal
from guanghe_companion.chat_memory_plans import prepare_plan, record_plan
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("mode", ["auto", "review"])
def test_semantic_correction_preserves_future_plan(tmp_path, legacy, mode):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    if legacy:
        memory.remember(kind="玩家希望被记住", title="搬家", summary="我下个月要搬去天津。",
                        source="explicit_user_request", now=10, user_confirmed=True)
    else:
        record_plan(memory, prepare_plan("我下个月要搬去天津。"), now=10, mode="auto")
    old = memory.store.load_memories()[0]
    extraction = ChatMemoryExtraction(memory)
    text = "不对，我搬去的是青岛，不是天津。"
    envelope = extraction.prepare(text, now=20, mode=mode, generation=0)
    proposal = MemoryProposal("correct", "我搬去的是青岛", "青岛", "residence", "居住地",
                              (old.memory_id,), "explicit", "personal")
    result = extraction.apply(envelope, (proposal,), now=20, mode=mode, generation=0)
    if mode == "review":
        assert result.status == "pending"
        key = next(iter(memory.pending_candidates))
        memory.confirm_candidate(key, now=21)
    active = [entry for entry in memory.store.load_memories() if entry.is_active(now=21)]
    assert len(active) == 1
    assert "青岛" in active[0].summary and "天津" not in active[0].summary
    assert "计划" in active[0].summary and "未确认完成" in active[0].summary
    assert active[0].metadata["plan_status"] == "planned"
    assert active[0].metadata["time_expression"] == "下个月"
    assert "用户住在青岛" not in active[0].summary


def test_correction_exchange_cannot_reintroduce_replaced_place_after_restart(tmp_path):
    from guanghe_companion.dialogue import DialogueRequest
    from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController

    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    memory = c.story_runtime.memory
    record_plan(memory, prepare_plan("我下个月要搬去天津。"), now=0, mode="auto")
    old = memory.store.load_memories()[0]
    text = "不对，我搬去的是青岛，不是天津。"
    envelope = c.chat_memory_extraction.prepare(text, now=0, mode="auto", generation=c.host_context_generation)
    c.last_chat_memory_result = c.chat_memory_extraction.apply(envelope,
        (MemoryProposal("correct", "我搬去的是青岛", "青岛", "residence", "居住地",
                        (old.memory_id,), "explicit", "personal"),),
        now=0, mode="auto", generation=c.host_context_generation)
    ticket = c.prepare_host_dialogue(DialogueRequest(text), include_ai_expression=False, memory_prepared=False)
    c.complete_host_dialogue(ticket)
    assert c.dialogue_history
    c.close()
    reopened = PluginEnabledCompanionController(user_data_root=tmp_path)
    try:
        assert "天津" not in str(reopened.get_expression_context())
    finally:
        reopened.close()
