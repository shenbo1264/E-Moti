import pytest

from guanghe_companion.chat_memory import ChatMemory, ChatMemoryResult, spoken_memory_result
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.fixture
def chat(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    return ChatMemory(memory, tmp_path / "chat.json")


@pytest.mark.parametrize("connector", ["也", "还"])
@pytest.mark.parametrize("repeated", [False, True])
def test_coordinated_preferences_keep_negative_clause_and_source(chat, connector, repeated):
    if repeated:
        assert chat.process("我喜欢茉莉茶。", now=1).status == "saved"
    text = f"我喜欢茉莉茶，{connector}不喜欢油腻。"
    result = chat.process(text, now=2)
    assert result.status == "saved"
    rows = chat.memory.store.load_memories()
    assert {row.summary for row in rows} == {"用户喜欢茉莉茶", "用户不喜欢油腻"}
    negative = next(row for row in rows if row.summary == "用户不喜欢油腻")
    assert negative.metadata["original_quote"] == text
    assert negative.metadata["fact_slot"].endswith(":avoid")
    assert negative.source_ids
    assert not chat.memory.pending_candidates


def test_inherited_chain_can_continue_into_positive_preference(chat):
    assert chat.process("我住在厦门，也不喜欢油腻，还喜欢茉莉茶。", now=1).status == "saved"
    assert {row.summary for row in chat.memory.store.load_memories()} == {
        "用户住在厦门", "用户不喜欢油腻", "用户喜欢茉莉茶"}


@pytest.mark.parametrize("text", [
    "也不喜欢油腻。",
    "朋友喜欢茉莉茶，也不喜欢油腻。",
    "如果我喜欢茉莉茶，也不喜欢油腻。",
    "我喜欢茉莉茶，朋友喜欢果汁，也不喜欢油腻。",
    "我喜欢茉莉茶，因为天气热，也不喜欢油腻。",
    "我喜欢茉莉茶。也不喜欢油腻。",
    "我喜欢朋友喜欢的花，也不喜欢油腻。",
    "请叫我小岚，也不喜欢油腻。",
])
def test_subject_is_not_inherited_from_unsupported_or_unrelated_clause(chat, text):
    chat.process(text, now=1)
    assert not any(row.summary == "用户不喜欢油腻" for row in chat.memory.store.load_memories())


def test_clarification_speech_does_not_read_technical_receipt():
    receipt = ChatMemoryResult("clarify", "这条信息需要明确内容或目标后再处理。")
    spoken = spoken_memory_result(receipt)
    assert spoken != receipt.message
    assert "哪件事" in spoken
    assert not any(word in spoken for word in ("目标", "处理", "信息"))
    assert receipt.message == "这条信息需要明确内容或目标后再处理。"
