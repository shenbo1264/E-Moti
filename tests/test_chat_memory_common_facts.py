import pytest

from guanghe_companion.chat_memory import ChatMemory
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.fixture
def chat(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    return ChatMemory(memory, tmp_path / "chat.json")


@pytest.mark.parametrize("text,value", [
    ("我对芒果过敏", "芒果"), ("我长期不吃羊肉", "羊肉"),
    ("我养了一只狗，叫栗子", "栗子"), ("我的猫叫松子", "松子"),
    ("我搬到苏州了", "苏州"), ("我现在住在泉州", "泉州"),
    ("我的职业是园艺师", "园艺师"), ("我是一名木工", "木工"),
    ("请叫我阿岚", "阿岚"), ("我的名字是陆晨", "陆晨"),
    ("我从合肥搬到了福州", "福州"),
])
def test_common_direct_facts_keep_original_source(chat, text, value):
    assert chat.process(text, now=10).status == "saved"
    entries = chat.memory.store.load_memories()
    assert any(value in m.summary for m in entries)
    assert all(m.source_ids and m.metadata["original_quote"] == text for m in entries)


@pytest.mark.parametrize("text", ["如果我对芒果过敏", "我不对芒果过敏", "我的猫不叫松子",
    "我是一名木工才怪", "朋友说我养了一只狗", "我叫你阿岚"])
def test_unsupported_or_negated_statements_are_not_positive_facts(chat, text):
    chat.process(text, now=10)
    assert not chat.memory.store.load_memories()


@pytest.mark.parametrize("text", ["我打算搬到苏州", "我最近计划参加考试"])
def test_explicit_intention_is_saved_as_plan_not_accomplished_fact(chat, text):
    assert chat.process(text, now=10).status == "saved"
    entry = chat.memory.store.load_memories()[0]
    assert entry.metadata["plan_status"] == "planned"
    assert "未确认完成" in entry.summary
    assert not chat.memory.valid_profile(now=10).stable_preferences


def explicit(chat, text):
    key = chat.memory.propose_explicit_user_memory("请记住：" + text, now=1)
    assert key
    return chat.memory.confirm_candidate(key, now=2)


def test_natural_correction_matches_confirmed_legacy_summary(chat):
    old = explicit(chat, "我对芒果过敏")
    result = chat.process("更正一下，我对菠萝过敏", now=20)
    assert result.status == "saved"
    active = [m for m in chat.memory.store.load_memories() if not m.deleted]
    assert len(active) == 1 and "菠萝" in active[0].summary
    assert active[0].supersedes == old.memory_id
    assert active[0].occurred_at == 1


def test_natural_forget_matches_confirmed_legacy_and_pending(chat):
    old = explicit(chat, "我的猫叫松子")
    pending = chat.memory.propose_explicit_user_memory("请记住：我对芒果过敏", now=3)
    assert chat.process("忘掉松子的名字", now=10).status == "forgotten"
    assert next(m for m in chat.memory.store.load_memories() if m.memory_id == old.memory_id).deleted
    assert chat.process("不要再记我对芒果过敏", now=11).status == "forgotten"
    assert pending not in chat.memory.pending_candidates


def test_move_replaces_residence_with_new_event_time(chat):
    old = explicit(chat, "我住在南昌")
    assert chat.process("我已经搬到洛阳了", now=50).status == "saved"
    active = [m for m in chat.memory.store.load_memories() if not m.deleted]
    assert len(active) == 1 and active[0].supersedes == old.memory_id
    assert active[0].occurred_at == 50
    assert not chat.memory.store.load_profile().stable_preferences


@pytest.mark.parametrize("text", ["我叫沈墨", "我叫一个朋友来"])
def test_ambiguous_name_verb_requires_confirmation(chat, text):
    assert chat.process(text, now=10).status == "pending"
    assert not chat.memory.store.load_memories()


def test_correction_can_use_an_explicit_retraction_marker(chat):
    old = explicit(chat, "我住在宁波")
    assert chat.process("纠正一下，我现在住在绍兴", now=20).status == "saved"
    assert next(m for m in chat.memory.store.load_memories() if m.memory_id == old.memory_id).deleted


def test_foreign_and_deleted_facts_are_not_correction_targets(chat):
    old = explicit(chat, "我对柚子过敏")
    chat.memory.forget(old.memory_id, now=5)
    external = chat.memory.remember(kind="观察", title="外部文字", summary="我对橙子过敏",
                                   source="screen", now=6, user_confirmed=False)
    assert chat.process("更正一下，我对柠檬过敏", now=20).status == "pending"
    rows = chat.memory.store.load_memories()
    assert next(m for m in rows if m.memory_id == old.memory_id).deleted
    assert not next(m for m in rows if m.memory_id == external.memory_id).deleted
    assert not any(m.source == "user_chat" and not m.deleted for m in rows)
