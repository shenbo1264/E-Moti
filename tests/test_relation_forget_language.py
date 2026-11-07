import pytest

from guanghe_companion.chat_memory import ChatMemory
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.mark.parametrize("statement,command,kept", [
    ("我的领队叫顾宁。", "请忘记我的领队叫什么名字。", "我的领队住在青石街。"),
    ("我的邻居住在青石街。", "请忘记我的邻居住在哪里。", "我的邻居叫顾宁。"),
    ("我的搭档的职业是设计师。", "请忘记我的搭档做什么工作。", "我的搭档叫顾宁。"),
])
def test_natural_field_question_inside_forget_retires_only_that_field(tmp_path, statement, command, kept):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    chat = ChatMemory(memory, tmp_path / "chat-settings.json")
    assert chat.process(statement, now=10).status == "saved"
    assert chat.process(kept, now=11).status == "saved"
    result = chat.process(command, now=12)
    assert result.status == "forgotten"
    memory.close()
    reopened = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    rows = [entry.summary for entry in reopened.store.load_memories() if entry.is_active(now=13)]
    assert len(rows) == 1
    assert kept.removeprefix("我的").rstrip("。") in rows[0]
    reopened.close()
