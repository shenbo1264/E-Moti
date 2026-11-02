"""Old explicit saves need literal verification when no typed slot exists."""
import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.mark.parametrize("statement,query", [
    ("我周末练习的乐器是中阮。", "我周末练习哪种乐器？"),
    ("我常去的图书馆已经改成海棠图书馆。", "现在我常去哪家图书馆？"),
    ("我早餐用的杯子是蓝色马克杯。", "我早餐用哪种杯子？"),
    ("坐火车时我偏爱靠过道的座位，方便起身。", "帮我回想一下坐火车时的座位偏好？"),
    ("坐飞机时我喜欢靠窗的座位。", "坐飞机时我的座位偏好是什么？"),
])
def test_saved_literal_attribute_can_be_verified_without_inference(tmp_path, statement, query):
    memory = EmotionalMemoryService(root=tmp_path, character_id="pet")
    row = memory.remember(kind="用户偏好", title="用户主动记住", summary=statement,
                          source="explicit_user_request", now=1, source_ids=("turn:1",))
    result = memory.retrieve(query, now=2)
    assert result.trace.status == "sufficient"
    assert [e.memory_id for e in result.bundle.memories] == [row.memory_id]
    assert memory.store.load_memories()[0].metadata == {}  # read-only derivation


@pytest.mark.parametrize("statement,query,source", [
    ("我周末练习的乐器是中阮。", "我工作日练习哪种乐器？", "explicit_user_request"),
    ("我常去的图书馆是海棠图书馆。", "我常去哪家游泳馆？", "explicit_user_request"),
    ("我的朋友周末练习的乐器是中阮。", "我周末练习哪种乐器？", "explicit_user_request"),
    ("我周末练习的乐器是中阮。", "我周末练习哪种乐器？", "assistant_generated"),
    ("如果我周末练习的乐器是中阮。", "我周末练习哪种乐器？", "explicit_user_request"),
    ("坐火车时我偏爱靠过道的座位。", "坐飞机时我的座位偏好是什么？", "explicit_user_request"),
    ("坐火车时我偏爱靠过道的座位。", "坐火车时我的饮品偏好是什么？", "explicit_user_request"),
])
def test_similar_literal_must_not_cross_subject_field_context_or_trust(tmp_path, statement, query, source):
    memory = EmotionalMemoryService(root=tmp_path, character_id="pet")
    memory.remember(kind="用户偏好", title="用户主动记住", summary=statement,
                    source=source, now=1, source_ids=("turn:1",))
    assert not memory.retrieve(query, now=2).bundle.memories
