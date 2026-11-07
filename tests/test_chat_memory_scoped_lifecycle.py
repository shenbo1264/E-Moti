from guanghe_companion.chat_memory import ChatMemory
from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
import pytest


def apply(memory, text, value, action="remember", ids=(), now=10):
    extraction = ChatMemoryExtraction(memory)
    envelope = extraction.prepare(text, now=now, mode="auto", generation=1)
    proposal = MemoryProposal(action, text, value, "like", "个人偏好", ids, "explicit", "personal")
    return extraction.apply(envelope, (proposal,), now=now, mode="auto", generation=1)


def test_legacy_like_preserves_context_and_person_then_scoped_forget(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    first = apply(memory, "我做书签最喜欢竹叶图案。", "竹叶图案")
    other = apply(memory, "我的姐姐做书签最喜欢兰花图案。", "兰花图案")
    assert other.status == "saved"
    revised = apply(memory, "我现在做书签最喜欢的图案改成海浪了。", "海浪", "correct", first.memory_ids, 11)
    assert revised.status == "saved"
    active = [m for m in memory.store.load_memories() if m.is_active(now=11)]
    assert len(active) == 2
    assert all("做书签" in m.summary for m in active)
    assert {m.metadata["fact_subject"] for m in active} == {"user:self", "relation:姐姐"}
    chat = ChatMemory(memory, tmp_path / "settings.json")
    assert chat.process("请忘记我自己做书签的图案偏好。", now=12).status == "forgotten"
    active = [m for m in memory.store.load_memories() if m.is_active(now=12)]
    assert [m.memory_id for m in active] == list(other.memory_ids)


def test_existing_weekly_change_and_forget_use_same_activity_binding(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    chat = ChatMemory(memory, tmp_path / "settings.json")
    assert chat.process("我每周三晚上去参加陶艺练习。", now=10).status == "saved"
    assert chat.process("陶艺练习以后改到每周六晚上了，我也改在这个时间去。", now=11).status == "saved"
    active = [m for m in memory.store.load_memories() if m.is_active(now=11)]
    assert len(active) == 1 and "周六晚上" in active[0].summary and "周三" not in active[0].summary
    assert chat.process("请忘记我参加陶艺练习的时间。", now=12).status == "forgotten"
    assert not any(m.is_active(now=12) for m in memory.store.load_memories())


@pytest.mark.parametrize("text", ["我的邻居喜欢清茶。", "我邻居最喜欢清茶。"])
def test_unbound_personal_preference_never_becomes_user_preference(tmp_path, text):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    assert apply(memory, text, "清茶").status == "clarify"
    assert not memory.store.load_memories()


def test_weekly_report_about_another_person_does_not_change_users_schedule(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    chat = ChatMemory(memory, tmp_path / "settings.json")
    chat.process("我每周三晚上去参加陶艺练习。", now=10)
    chat.process("我听说同事陶艺练习改到每周六晚上。", now=11)
    assert all("周三" in m.summary for m in memory.store.load_memories() if m.is_active(now=11))


def test_explicit_scope_selects_own_unique_target_instead_of_models_other_person_id(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    own = apply(memory, "我做书签最喜欢竹叶图案。", "竹叶图案")
    other = apply(memory, "我的姐姐做书签最喜欢兰花图案。", "兰花图案")
    revised = apply(memory, "我现在做书签最喜欢的图案改成海浪了。", "海浪", "correct", other.memory_ids, 11)
    assert revised.status == "saved"
    active = [m for m in memory.store.load_memories() if m.is_active(now=11)]
    assert len(active) == 2
    assert any(m.memory_id == other.memory_ids[0] for m in active)
    assert not any(m.memory_id == own.memory_ids[0] for m in active)


def test_unique_literal_old_value_preserves_scoped_preference_when_scope_is_omitted(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    first = apply(memory, "我周末听播客最常听《林间读信》。", "《林间读信》")
    text = "最近我换成固定听《午后手记》了，《林间读信》现在不听了。"
    result = apply(memory, text, "《午后手记》", "correct", first.memory_ids, 11)
    assert result.status == "saved"
    active = [m for m in memory.store.load_memories() if m.is_active(now=11)]
    assert active[0].metadata["preference_context"] == "听播客"
    assert "听播客" in active[0].summary
