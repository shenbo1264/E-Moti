import pytest

from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal
from guanghe_companion.expression_request import ExpressionRequest
from guanghe_companion.plugin_enabled_controller import PluginEnabledCompanionController


@pytest.mark.parametrize("mode", ["auto", "review"])
@pytest.mark.parametrize("scene", ["personal", "other"])
@pytest.mark.parametrize("predicate,domain", [("name", "称呼"), ("teacher_name", "教师姓名")])
def test_teacher_correction_preserves_relation_after_restart(tmp_path, mode, scene, predicate, domain):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    memory = c.story_runtime.memory
    key = memory.propose_explicit_user_memory("请记住：我的吉他老师叫林澈。", now=0)
    old = memory.confirm_candidate(key, now=0)
    extractor = ChatMemoryExtraction(memory)
    text = "刚才我写错老师的名字了，我的吉他老师叫江屿。"
    envelope = extractor.prepare(text, now=0, mode=mode, generation=c.host_context_generation)
    proposal = MemoryProposal("correct", "我的吉他老师叫江屿", "江屿", predicate, domain,
                              (old.memory_id,), "explicit", scene)
    result = extractor.apply(envelope, (proposal,), now=0, mode=mode, generation=c.host_context_generation)
    assert result.status == ("pending" if mode == "review" else "saved")
    if mode == "review":
        memory.confirm_candidate(next(iter(memory.pending_candidates)), now=0)
    c.close()
    restarted = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=True)
    try:
        current = [m for m in restarted.story_runtime.memory.store.load_memories() if not m.deleted]
        assert len(current) == 1
        assert current[0].summary == "用户的吉他老师叫江屿"
        assert current[0].metadata["fact_slot"] == "teacher_name:吉他老师"
        restarted._current_player_message = "我学吉他的老师叫什么？"
        def prompt():
            return restarted.ai_expressor.build_prompt(ExpressionRequest.from_snapshot(
                restarted.get_typed_snapshot(), context=restarted.get_expression_context()))
        assert "江屿" in prompt() and "林澈" not in prompt()
        restarted.memory_album_controller.forget(current[0].memory_id, now=int(restarted.now))
        assert "江屿" not in prompt() and "林澈" not in prompt()
    finally:
        restarted.close()


@pytest.mark.parametrize("old_text,new_text", [
    ("我的钢琴老师叫林澈。", "我的吉他老师叫江屿"),
    ("我的姓名是林澈。", "我的吉他老师叫江屿"),
    ("我的吉他老师叫林澈。", "我叫江屿"),
])
def test_teacher_name_cannot_replace_another_person(tmp_path, old_text, new_text):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        memory = c.story_runtime.memory
        old = memory.confirm_candidate(memory.propose_explicit_user_memory("请记住：" + old_text, now=0), now=0)
        extractor = ChatMemoryExtraction(memory)
        envelope = extractor.prepare("我说错了，" + new_text, now=0, mode="auto", generation=0)
        p = MemoryProposal("correct", new_text, "江屿", "name", "称呼", (old.memory_id,), "explicit", "personal")
        result = extractor.apply(envelope, (p,), now=0, mode="auto", generation=0)
        assert result.status in {"ignored", "clarify"}
        active = [m.summary for m in memory.store.load_memories() if not m.deleted]
        assert len(active) == 1 and "林澈" in active[0] and "江屿" not in active[0]
    finally:
        c.close()


def test_teacher_forget_works_with_memory_off_and_keeps_user_identity(tmp_path):
    c = PluginEnabledCompanionController(user_data_root=tmp_path, auto_load=False)
    try:
        memory = c.story_runtime.memory
        teacher = memory.confirm_candidate(memory.propose_explicit_user_memory("请记住：我的吉他老师叫江屿。", now=0), now=0)
        user = memory.confirm_candidate(memory.propose_explicit_user_memory("请记住：我的名字是许安。", now=0), now=0)
        extractor = ChatMemoryExtraction(memory)
        text = "请忘掉我的吉他老师"
        envelope = extractor.prepare(text, now=0, mode="off", generation=0)
        p = MemoryProposal("forget", text, "", "teacher_name", "教师姓名", (teacher.memory_id,), "explicit", "other")
        result = extractor.apply(envelope, (p,), now=0, mode="off", generation=0)
        assert result.status == "forgotten"
        active = [m for m in memory.store.load_memories() if not m.deleted]
        assert [m.memory_id for m in active] == [user.memory_id]
    finally:
        c.close()
