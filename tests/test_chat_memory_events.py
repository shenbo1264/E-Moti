from dataclasses import replace

import pytest

from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal, should_extract
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


def proposal(text, *, anchor="还书约定", status="planned", participants=("我", "阿岑"),
             time_text="周五", action="remember", targets=()):
    return MemoryProposal(action, text, text, "event", "日常事件", targets, "explicit", "personal",
        event={"anchor": anchor, "status": status, "participants": list(participants), "time_text": time_text})


def apply(service, text, rows, now=10, mode="auto"):
    extraction = ChatMemoryExtraction(service)
    envelope = extraction.prepare(text, now=now, mode=mode, generation=1)
    return extraction.apply(envelope, rows, now=now, generation=1, mode=mode)


def test_ordinary_commitment_persists_with_source_and_no_profile_mutation(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我和阿岑的还书约定是周五下午。"
    result = apply(memory, text, (proposal(text),))
    assert result.status == "saved"
    memory.close()
    reopened = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = reopened.store.load_memories()[0]
    assert entry.summary == text
    assert entry.metadata["event_status"] == "planned"
    assert entry.metadata["participants"] == ["user:self", "person:阿岑"]
    assert entry.metadata["time_expression"] == "周五"
    assert entry.metadata["source_claim_digest"]
    assert entry.source_ids
    assert entry.valid_until == 0


def test_reschedule_cancel_forget_preserve_unrelated_event(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    original = "我和阿岑的还书约定是周五下午。"
    first = apply(memory, original, (proposal(original),))
    unrelated = "我和阿岑周日去看展览。"
    other = apply(memory, unrelated, (proposal(unrelated, anchor="看展览", time_text="周日"),), now=11)
    changed = "我和阿岑的还书约定改到周六。"
    revised = apply(memory, changed, (proposal(changed, time_text="周六", action="correct", targets=first.memory_ids),), now=12)
    assert revised.status == "saved"
    active = [entry for entry in memory.store.load_memories() if entry.is_active(now=12)]
    assert len(active) == 2
    assert all("周五" not in entry.summary for entry in active)
    cancelled = "我取消和阿岑的还书约定。"
    ended = apply(memory, cancelled, (proposal(cancelled, status="cancelled", time_text="", action="correct", targets=revised.memory_ids),), now=13)
    assert ended.status == "saved"
    row = next(entry for entry in memory.store.load_memories() if entry.memory_id == ended.memory_ids[0])
    assert row.metadata["event_status"] == "cancelled"
    forget = "忘掉还书约定。"
    forgotten = replace(proposal(forget), action="forget", quote=forget, value="还书约定", target_ids=ended.memory_ids, event=None)
    assert apply(memory, forget, (forgotten,), now=14).status == "forgotten"
    assert [entry.memory_id for entry in memory.store.load_memories() if entry.is_active(now=14)] == list(other.memory_ids)


@pytest.mark.parametrize("status,text", [
    ("completed", "我和阿岑的铜铃修复已经完成。"),
    ("not_occurred", "我和阿岑的铜铃修复还没有开始。"),
])
def test_event_state_is_not_profile_or_shared_with_character(tmp_path, status, text):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    result = apply(memory, text, (proposal(text, anchor="铜铃修复", status=status, time_text=""),))
    row = next(entry for entry in memory.store.load_memories() if entry.memory_id in result.memory_ids)
    assert row.metadata["event_status"] == status
    assert "character:self" not in row.metadata["participants"]
    assert row.metadata["fact_domain"] == "日常事件"


def test_shared_completed_event_requires_literal_character_participation(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我和你聊着天完成了纸灯装饰。"
    result = apply(memory, text, (proposal(text, anchor="纸灯装饰", status="completed", participants=("我", "你"), time_text=""),))
    row = next(entry for entry in memory.store.load_memories() if entry.memory_id in result.memory_ids)
    assert row.metadata["participants"] == ["user:self", "character:self"]


@pytest.mark.parametrize("text", ["我明天准备去办证。", "我今天借了同事的三脚架。", "我和小河约好周六见面。"])
def test_short_term_event_is_eligible_for_controlled_extraction(text):
    assert should_extract(text)


@pytest.mark.parametrize("text", ["如果我明天去办证。", "朋友说我明天去办证。", "我明天要去办证吗？"])
def test_nonasserted_event_is_not_saved(tmp_path, text):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    assert apply(memory, text, (proposal(text, anchor="办证", participants=("我",), time_text="明天"),)).status == "ignored"
    assert not memory.store.load_memories()


def test_event_correction_cannot_target_another_anchor(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    original = "我和阿岑的还书约定是周五。"
    first = apply(memory, original, (proposal(original),))
    text = "我和阿岑的看展览改到周六。"
    result = apply(memory, text, (proposal(text, anchor="看展览", action="correct", targets=first.memory_ids, time_text="周六"),), now=11)
    assert result.status == "clarify"
    assert memory.store.load_memories()[0].is_active(now=11)


def test_event_review_and_off_follow_memory_setting(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我和阿岑的还书约定是周五。"
    assert apply(memory, text, (proposal(text),), mode="off").status == "ignored"
    assert apply(memory, text, (proposal(text),), mode="review").status == "pending"
    assert not memory.store.load_memories()
    assert memory.pending_candidates


def test_temporary_preference_is_not_promoted_to_long_term_profile(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我今天喜欢喝浓咖啡。"
    item = MemoryProposal("remember", text, "浓咖啡", "like", "个人偏好", (), "explicit", "personal")
    assert apply(memory, text, (item,)).status == "ignored"
    assert not memory.store.load_memories()


@pytest.mark.parametrize("text,status", [
    ("我已经预约了下周检查。", "completed"),
    ("我计划了周末露营。", "completed"),
    ("我昨天完成了铜铃修复。", "planned"),
    ("我在信里引用了‘你已经完成铜铃修复’。", "completed"),
])
def test_event_state_does_not_promote_preparation_or_quote_to_completion(tmp_path, text, status):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    item = proposal(text, anchor="检查" if "检查" in text else "露营" if "露营" in text else "铜铃修复",
        status=status, participants=("我",), time_text="下周" if "下周" in text else "周末" if "周末" in text else "昨天" if "昨天" in text else "")
    try:
        result = apply(memory, text, (item,))
        assert result.status == "ignored"
    except ValueError:
        pass
    assert not memory.store.load_memories()


def test_borrow_and_return_are_distinct_atomic_states(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我昨天借了阿岑的折叠梯，约定周五归还。"
    borrowed = proposal("我昨天借了阿岑的折叠梯", anchor="折叠梯", status="completed", time_text="昨天")
    borrowed = replace(borrowed, event={**borrowed.event, "activity": "借", "context_quote": text})
    planned = proposal("约定周五归还", anchor="折叠梯", status="planned", time_text="周五")
    planned = replace(planned, event={**planned.event, "activity": "归还", "context_quote": text})
    result = apply(memory, text, (borrowed, planned))
    assert result.status == "saved"
    active = memory.store.load_memories()
    assert len(active) == 2
    assert {entry.metadata["event_status"] for entry in active} == {"completed", "planned"}
    returned = next(entry for entry in active if entry.metadata["event_status"] == "planned")
    assert "借了" not in returned.summary
    assert "阿岑" in returned.summary and "折叠梯" in returned.summary
    assert returned.metadata["source_support_spans"]


@pytest.mark.parametrize("text,anchor", [("我提交了摘要。", "摘要"), ("我见过将军。", "将军")])
def test_completed_claim_does_not_treat_noun_characters_as_modality(tmp_path, text, anchor):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    result = apply(memory, text, (proposal(text, anchor=anchor, status="completed", participants=("我",), time_text=""),))
    assert result.status == "saved"


def test_event_target_selection_is_relevant_and_bounded_in_larger_archive(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    for index in range(15):
        text = f"我和阿岑的物品{index}归还是周五。"
        apply(memory, text, (proposal(text, anchor=f"物品{index}"),), now=index + 10)
    text = "我和阿岑的折叠梯归还约定是周五。"
    target = apply(memory, text, (proposal(text, anchor="折叠梯"),), now=30)
    for index in range(15, 30):
        text = f"我和阿岑的物品{index}归还是周五。"
        apply(memory, text, (proposal(text, anchor=f"物品{index}"),), now=index + 31)
    extraction = ChatMemoryExtraction(memory)
    envelope = extraction.prepare("我和阿岑的折叠梯归还约定改到周六。", now=70, mode="auto", generation=1)
    assert len(envelope.facts) <= 12
    assert target.memory_ids[0] in {fact.memory_id for fact in envelope.facts}
