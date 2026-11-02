import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.mark.parametrize("statement,query,name", [
    ("我养了一只叫米糕的橘猫", "我的猫叫什么", "米糕"),
    ("我养了一只叫松果的长毛兔子", "我的兔子叫什么", "松果"),
    ("我拥有一只叫青豆的鹦鹉", "我的鹦鹉叫什么", "青豆"),
])
def test_explicit_owned_pet_name_survives_restart_without_dialogue(tmp_path, statement, query, name):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    pending = service.propose_explicit_user_memory("请记住：" + statement, now=10)
    entry = service.confirm_candidate(pending, now=10)
    reopened = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    result = reopened.retrieve(query, now=20, history=())
    assert result.trace.status == "sufficient"
    assert entry.memory_id in {row.memory_id for row in result.bundle.memories}
    assert name in result.bundle.memories[0].summary
    assert not reopened.retrieve("我叫什么名字", now=20).bundle.memories


@pytest.mark.parametrize("statement", [
    "我养了一只橘猫", "我的朋友养了一只叫米糕的橘猫", "我想养一只叫米糕的橘猫",
])
def test_name_must_be_explicit_and_belong_to_users_pet(tmp_path, statement):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    pending = service.propose_explicit_user_memory("请记住：" + statement, now=10)
    service.confirm_candidate(pending, now=10)
    assert not service.retrieve("我的猫叫什么", now=20).bundle.memories
