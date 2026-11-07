from dataclasses import replace
import pytest

from guanghe_companion.chat_memory import ChatMemory
from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


def proposal(text, subject, field, value, action="remember", targets=()):
    return MemoryProposal(action, text, value, "attribute", "对象属性", targets, "explicit", "personal",
        fact={"subject": subject, "field": field})


def apply(memory, text, rows, now=10):
    extraction = ChatMemoryExtraction(memory)
    prepared = extraction.prepare(text, now=now, mode="auto", generation=1)
    return extraction.apply(prepared, rows, now=now, mode="auto", generation=1)


def test_generic_attribute_correction_restart_and_scoped_forget(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的路由器频道是44。"
    first = apply(memory, text, (proposal(text, "路由器", "频道", "44"),))
    other = "我的路由器名字是云舟。"
    retained = apply(memory, other, (proposal(other, "路由器", "名字", "云舟"),), now=11)
    text = "我把路由器频道改为36。"
    revised = apply(memory, text, (proposal(text, "路由器", "频道", "36", "correct", first.memory_ids),), now=12)
    assert revised.status == "saved"
    memory.close()
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    active = [entry for entry in memory.store.load_memories() if entry.is_active(now=13)]
    assert {entry.metadata["fact_value"] for entry in active} == {"36", "云舟"}
    chat = ChatMemory(memory, tmp_path / "settings.json")
    result = chat.process("请删除并忘记我的路由器频道，旧的和新的都不要记。", now=14)
    assert result.status == "forgotten"
    active = [entry for entry in memory.store.load_memories() if entry.is_active(now=14)]
    assert [entry.memory_id for entry in active] == list(retained.memory_ids)


def test_independent_preference_subjects_do_not_conflict(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    for text, subject, value in [("我挑围巾喜欢细条纹。", "围巾", "细条纹"), ("我选鼠标喜欢静音款。", "鼠标", "静音款")]:
        assert apply(memory, text, (proposal(text, subject, "偏好", value),)).status == "saved"
    assert len(memory.store.load_memories()) == 2
    assert not memory.pending_candidates


def test_attribute_cannot_correct_another_subject_or_field(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的电台频率是89。"
    first = apply(memory, text, (proposal(text, "电台", "频率", "89"),))
    text = "我的路由器频道现在是36。"
    result = apply(memory, text, (proposal(text, "路由器", "频道", "36", "correct", first.memory_ids),), now=11)
    assert result.status == "clarify"
    assert memory.store.load_memories()[0].is_active(now=11)


def test_unique_existing_field_can_bind_explicit_change_without_repeating_subject(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的音箱音量是20。"
    first = apply(memory, text, (proposal(text, "音箱", "音量", "20"),))
    text = "我现在从20改成30了。"
    result = apply(memory, text, (proposal(text, "音箱", "音量", "30", "correct", first.memory_ids),), now=11)
    assert result.status == "saved"
    active = [entry for entry in memory.store.load_memories() if entry.is_active(now=11)]
    assert active[0].metadata["attribute_subject"] == "音箱"
    assert "20" not in active[0].summary


def test_atomic_correction_inherits_explicit_user_scope_from_current_binding(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的扳手放在工具盒。"
    first = apply(memory, text, (proposal(text, "扳手", "位置", "工具盒"),))
    text = "我换了位置，扳手现在放在抽屉里，工具盒不放了。"
    item = proposal("扳手现在放在抽屉里", "扳手", "位置", "抽屉里", "correct", first.memory_ids)
    assert apply(memory, text, (item,), now=11).status == "saved"


def test_copular_content_attribute_is_supported_without_field_name_in_source(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的锁屏画面是海上日出。"
    assert apply(memory, text, (proposal(text, "锁屏画面", "内容", "海上日出"),)).status == "saved"


def test_single_existing_attribute_does_not_authorize_new_subject_rebinding(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的杯子颜色是白色。"
    first = apply(memory, text, (proposal(text, "杯子", "颜色", "白色"),))
    text = "我的背包现在是绿色。"
    assert apply(memory, text, (proposal(text, "杯子", "颜色", "绿色", "correct", first.memory_ids),), now=11).status == "clarify"


def test_forget_long_object_name_preserves_short_named_independent_object(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    for name in ("水瓶", "保温水瓶"):
        text = f"我的{name}颜色是白色。"
        apply(memory, text, (proposal(text, name, "颜色", "白色"),))
    chat = ChatMemory(memory, tmp_path / "settings.json")
    assert chat.process("忘掉保温水瓶的颜色。", now=11).status == "forgotten"
    active = [entry for entry in memory.store.load_memories() if entry.is_active(now=11)]
    assert [entry.metadata["attribute_subject"] for entry in active] == ["水瓶"]


def test_event_literal_value_is_normalized_to_atomic_claim_and_repeat_is_ignored(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我已经借了阿河的螺丝刀。"
    item = MemoryProposal("remember", text, "螺丝刀", "event", "日常事件", (), "explicit", "personal",
        event={"anchor": "螺丝刀", "activity": "借", "status": "completed", "participants": ["我", "阿河"], "time_text": ""})
    assert apply(memory, text, (item,)).status == "saved"
    assert apply(memory, text, (item,), now=11).status == "ignored"
    assert len(memory.store.load_memories()) == 1
    assert memory.store.load_memories()[0].metadata["fact_value"] == text


@pytest.mark.parametrize("tail", ["但保留名字", "只忘颜色", "除了名字", "名字除外", "不要删除名字"])
def test_qualified_forget_does_not_discard_scope_restriction(tmp_path, tail):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我的播放器颜色是蓝色。"
    apply(memory, text, (proposal(text, "播放器", "颜色", "蓝色"),))
    text = "我的播放器名字是月牙。"
    apply(memory, text, (proposal(text, "播放器", "名字", "月牙"),))
    chat = ChatMemory(memory, tmp_path / "settings.json")
    assert chat.process("忘掉我的播放器信息，" + tail + "。", now=11).status == "clarify"
    assert len([entry for entry in memory.store.load_memories() if entry.is_active(now=11)]) == 2
