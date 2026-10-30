import pytest

from guanghe_companion.chat_memory_plans import PLAN_RETENTION_SECONDS, prepare_plan, record_plan, plan_view, correct_plan
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.fixture
def memory(tmp_path):
    return EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")


@pytest.mark.parametrize("text,time_text", [
    ("我下周要去泉州参加培训。", "下周"),
    ("我计划十一月搬去合肥。", "十一月"),
    ("刚才公交很挤。对了我在备考日语，九月参加考试。", "九月"),
    ("我打算学习木工。", ""),
])
def test_plan_keeps_literal_schedule_without_claiming_completion(memory, text, time_text):
    plan = prepare_plan(text)
    assert plan is not None and plan.time_expression == time_text
    assert record_plan(memory, plan, now=37, mode="auto").status == "saved"
    entry = memory.store.load_memories()[0]
    assert entry.metadata["plan_status"] == "planned"
    assert entry.metadata["original_quote"] == text
    assert entry.metadata["time_expression"] == time_text
    assert entry.valid_until == 37 + PLAN_RETENTION_SECONDS
    assert entry.occurred_at == 37 and "计划（未确认完成）" in entry.summary
    profile = memory.valid_profile(now=38)
    assert not profile.stable_preferences and not profile.player_alias


@pytest.mark.parametrize("text", ["如果我下周要搬家", "我原本打算周末去游泳", "我昨天已经搬去郑州了",
    "我朋友计划学习木工", "小说里我计划开店", "我计划下周出差吗？", "今天好困", "我不打算学木工",
    "我计划偷看银行卡密码", "假如我在备考法语", "我打算学陶艺才怪"])
def test_unasserted_or_completed_plans_are_not_recorded(text):
    assert prepare_plan(text) is None


def test_review_plan_ttl_survives_restart_and_confirmation(memory, tmp_path):
    plan = prepare_plan("我计划明年参加绘画课程")
    assert record_plan(memory, plan, now=30, mode="review").status == "pending"
    restarted = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    key, candidate = next(iter(restarted.pending_candidates.items()))
    assert candidate.valid_until == 30 + PLAN_RETENTION_SECONDS
    entry = restarted.confirm_candidate(key, now=50)
    assert entry.valid_until == 30 + PLAN_RETENTION_SECONDS
    assert entry.occurred_at == 30
    epoch = restarted.store.context_epoch
    restarted.store.expire_memories(now=entry.valid_until)
    assert restarted.store.context_epoch > epoch
    assert not restarted.recall("绘画课程", now=entry.valid_until)
    assert not restarted.store.upsert_memory(entry).is_active(now=entry.valid_until)


def test_plan_off_and_forgetting_use_same_memory_authority(memory):
    plan = prepare_plan("我下周要参加跑步比赛")
    assert record_plan(memory, plan, now=10, mode="off").status == "ignored"
    record_plan(memory, plan, now=10, mode="auto")
    entry = memory.store.load_memories()[0]
    memory.forget(entry.memory_id, now=11)
    assert not memory.recall("跑步", now=12)
    assert memory.store.upsert_memory(entry).deleted


@pytest.mark.parametrize("mode", ["auto", "review"])
def test_correct_legacy_plan_preserves_future_time_and_retires_derived(memory, mode):
    key = memory.propose_explicit_user_memory("请记住：我下个月要搬去南昌。", now=10)
    old = memory.confirm_candidate(key, now=11)
    memory.update_bond_profile(new_preference="南昌", source_memory_ids=(old.memory_id,), now=11)
    assert plan_view(old).time_expression == "下个月"
    result = correct_plan(memory, old, summary="用户住在洛阳", value="洛阳",
                          text="不对，我搬去的是洛阳，不是南昌。", now=20, mode=mode)
    if mode == "review":
        assert result.status == "pending"
        key, candidate = next(iter(memory.pending_candidates.items()))
        assert candidate.valid_until == 10 + PLAN_RETENTION_SECONDS
        assert candidate.metadata["supersedes_memory_id"] == old.memory_id
        replacement = memory.confirm_candidate(key, now=21)
    else:
        assert result.status == "saved"
        replacement = next(m for m in memory.store.load_memories() if not m.deleted)
    assert replacement.occurred_at == 10
    assert replacement.valid_until == 10 + PLAN_RETENTION_SECONDS
    assert replacement.metadata["plan_status"] == "planned"
    assert "洛阳" in replacement.summary and "南昌" not in replacement.summary
    assert "未确认完成" in replacement.summary and "下个月" in replacement.summary
    assert old.source_ids[0] in replacement.source_ids
    assert not memory.valid_profile(now=22).stable_preferences
    assert memory.store.upsert_memory(old).deleted


def test_correct_new_plan_preserves_existing_ttl_and_refuses_ambiguous_time(memory):
    record_plan(memory, prepare_plan("我下周要去成都参加课程"), now=5, mode="auto")
    old = memory.store.load_memories()[0]
    result = correct_plan(memory, old, summary="用户计划去重庆", value="重庆",
                          text="更正一下，我要去重庆", now=15, mode="auto")
    assert result.status == "saved"
    replacement = next(m for m in memory.store.load_memories() if not m.deleted)
    assert replacement.valid_until == old.valid_until
    assert plan_view(replacement).time_expression == "下周"
    assert correct_plan(memory, replacement, summary="用户去武汉", value="武汉",
                        text="我明年改去武汉", now=20, mode="auto").status == "clarify"
