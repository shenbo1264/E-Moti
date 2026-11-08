import json
from dataclasses import replace

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import validate_judgment, hard_eligibility
from guanghe_companion.retrieval_contract import RetrievalIntent, RetrievalPlan
from guanghe_companion.retrieval_evidence import check_eligibility
from guanghe_companion.retrieval_router import MemoryRetrievalRouter


def remember(service, text, **kwargs):
    return service.remember(kind="用户事实", title="来源状态", summary=text,
        source="explicit_user_request", source_ids=("utterance:one",), now=10, **kwargs)


@pytest.mark.parametrize("text", ["我和表姐一起预约的陶艺课是哪天？", "我跟林青一起做的模型叫什么？"])
def test_together_with_other_person_does_not_require_character_participation(text):
    plan = MemoryRetrievalRouter().plan(text, now=10)
    assert not any(intent.requires_shared_event for intent in plan.intents)


@pytest.mark.parametrize("text", ["我们一起做的模型叫什么？", "我和你一起做的模型叫什么？"])
def test_explicit_companion_together_still_requires_shared_proof(text):
    assert any(intent.requires_shared_event for intent in MemoryRetrievalRouter().plan(text, now=10).intents)


def test_archive_unix_basis_can_supply_missing_card_basis_but_not_override_logical(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = remember(service, "下一版编号从未来日期起生效。", valid_from=100)
    entry = replace(entry, metadata={})
    intent = RetrievalIntent("fact", "日期以后编号是多少", temporal_mode="as_of", as_of=110, as_of_end=120)
    args = dict(now=10, owner_id=service.owner_id, character_id=service.character_id, archive_time_basis="unix")
    assert check_eligibility(entry, intent, **args) is None
    assert check_eligibility(replace(entry, metadata={"time_basis": "logical"}), intent, **args).reason == "unresolved_time_basis_or_date"
    assert check_eligibility(entry, intent, **{**args, "archive_time_basis": "logical"}).reason == "unresolved_time_basis_or_date"


def judge(service, entry, query, *, use, route="episode", shared=False, occurrence=None):
    proof = {"id": entry.memory_id, "quote": entry.summary}
    if occurrence:
        proof["occurrence"] = occurrence
    if shared:
        proof["participants"] = ["user:self", "character:self"]
    return validate_judgment(json.dumps({"intents": [{"route": route, "question_ref": 0,
        "claim_use": use, "status": "sufficient", "evidence": [proof]}]}, ensure_ascii=False),
        query=query, plan=RetrievalPlan((RetrievalIntent(route, query,
            temporal_mode="history" if occurrence else "current", requires_shared_event=shared),)),
        entries=(entry,), now=10, owner_id=service.owner_id, character_id=service.character_id)


def test_explicit_negative_occurrence_overrides_inconsistent_completed_label(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = remember(service, "我的木笛从来没有换过簧片。")
    result = judge(service, entry, "以前换过簧片吗？", use="completed_event", occurrence="explicitly_not_occurred")
    assert result.source_ids == (entry.memory_id,)
    assert result.plan.intents[0].temporal_mode == "current"


@pytest.mark.parametrize("text,allowed", [
    ("我和钟遥约好下周在展馆看展，现在还没去。", True),
    ("如果我和钟遥约好下周看展，就带相机。", False),
    ("我和钟遥是否约好下周看展还不清楚。", False),
    ("我和钟遥上周已经看完展。", False),
])
def test_plan_use_requires_whole_grounded_plan_statement(tmp_path, text, allowed):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = remember(service, text)
    result = judge(service, entry, "约好的活动是什么？", use="planned_event", route="fact")
    assert bool(result.source_ids) == allowed


@pytest.mark.parametrize("text,allowed", [
    ("我跟你聊着天把风铃做好了，我们给它取名为晴音。", True),
    ("我跟钟遥聊着天把风铃做好了，我们给它取名为晴音。", False),
    ("我跟你约好下周做风铃，我们给它取名为晴音。", False),
    ("如果我跟你把风铃做好了，我们就给它取名为晴音。", False),
    ("我跟你下周过来布置展台。", False),
    ("我跟你了解这份图纸。", False),
    ("我跟你下周把展台布置好就可以了。", False),
    ("我跟你已经把风铃做好了，我们叫它晴音。", True),
])
def test_shared_claim_requires_explicit_companion_and_completed_source(tmp_path, text, allowed):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = remember(service, text)
    result = judge(service, entry, "我们做好的风铃叫什么？", use="completed_event", shared=True)
    assert bool(result.source_ids) == allowed


def test_textual_claim_cannot_bypass_revocation_or_executor_acceptance(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = remember(service, "我跟你把风铃做好了，我们叫它晴音。")
    for invalid in (replace(entry, deleted=True), replace(entry, owner_id="other"),
                    replace(entry, source="assistant"), replace(entry, source="executor")):
        assert not judge(service, invalid, "我们做好的风铃叫什么？", use="completed_event", shared=True).source_ids


def test_source_claim_is_rechecked_against_changed_quote_and_owner(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = remember(service, "我跟你把风铃做好了，我们叫它晴音。")
    result = judge(service, entry, "我们做好的风铃叫什么？", use="completed_event", shared=True)
    intent = result.plan.intents[0]
    claim = result.source_claims[0][entry.memory_id]
    args = dict(now=10, owner_id=service.owner_id, character_id=service.character_id, source_claim=claim)
    assert hard_eligibility(entry, intent, **args)
    assert not hard_eligibility(replace(entry, summary="只记得一个无关的计划。"), intent, **args)
    assert not hard_eligibility(replace(entry, owner_id="another"), intent, **args)
    assert not hard_eligibility(replace(entry, deleted=True), intent, **args)


@pytest.mark.parametrize("status", ["cancelled", "completed", "failed"])
def test_old_plan_text_cannot_override_explicit_event_state(tmp_path, status):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = remember(service, "我约好下周去看展。", metadata={"event_status": status})
    assert not judge(service, entry, "约好的活动是什么？", use="planned_event", route="fact").source_ids


def test_cancelled_literal_plan_is_not_current_plan(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = remember(service, "我约好下周去看展，但这个安排已经取消。")
    assert not judge(service, entry, "约好的活动是什么？", use="planned_event", route="fact").source_ids


def test_calendar_query_never_compares_explicit_logical_card(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = remember(service, "逻辑时间事实。")
    intent = RetrievalIntent("fact", "当时编号", temporal_mode="as_of", as_of=10, as_of_end=20)
    rejected = check_eligibility(entry, intent, now=30, owner_id=service.owner_id,
        character_id=service.character_id, archive_time_basis="unix")
    assert rejected is not None and rejected.reason == "unresolved_time_basis_or_date"
