"""The actual provider prompt must retain complete, attributable evidence."""
from copy import deepcopy
import json

from guanghe_companion.expression_prompt_budget import fit_prompt
from guanghe_companion.expression_request import _bounded_context


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _memory():
    return {
        "context_epoch": 9,
        "retrieval": {"status": "sufficient", "routes": ["episode"],
                      "intent_status": [{"route": "episode", "status": "sufficient",
                                         "source_ids": ["one", "two"]}]},
        "memory_overview": {"level": "L1", "catalog": {"event_count": 2, "period": [10, 20]},
                            "claims": [
                                {"text": "第一次画画。" * 40, "source_memory_id": "one",
                                 "source_fingerprint": "a" * 64, "occurred_at": 10},
                                {"text": "后来完成作品。" * 40, "source_memory_id": "two",
                                 "source_fingerprint": "b" * 64, "occurred_at": 20}]},
        "resolution_evidence": [{"memory_id": "binding", "summary": "作品别名。" * 40,
                                 "dependent_memory_ids": ["two"], "source_fingerprint": "c" * 64}],
    }


def _assert_complete(memory, original):
    claims = memory.get("memory_overview", {}).get("claims", [])
    assert claims
    assert all(claim in original["memory_overview"]["claims"] for claim in claims)
    assert memory["memory_overview"]["catalog"]["event_count"] == len(claims)
    assert memory["memory_overview"]["catalog"]["period"] == [
        min(c["occurred_at"] for c in claims), max(c["occurred_at"] for c in claims)]
    assert memory["retrieval"]["status"] == "insufficient"
    assert memory["retrieval"]["budget_limited"]
    assert not memory.get("resolution_evidence")
    assert memory["retrieval"]["intent_status"][0]["source_ids"] == ["one"]


def test_request_budget_trims_one_claim_and_its_dependent_binding():
    original = _memory()
    result = _bounded_context(original, budget=900)
    assert len(_encoded(result)) <= 900
    _assert_complete(result, original)
    assert original == _memory()


def test_provider_budget_keeps_persona_and_updates_partial_evidence():
    original = _memory()
    persona = {"character_id": "pet", "identity_version": "v4", "boundaries": ["不能编造共同经历"]}
    prompt = fit_prompt(["persona: " + _encoded(persona), "emotional_memory: " + _encoded(original)], limit=1000)
    payload = json.loads(next(line.split(": ", 1)[1] for line in prompt.splitlines()
                              if line.startswith("emotional_memory: ")))
    _assert_complete(payload, original)
    assert "identity_version" in prompt and "不能编造共同经历" in prompt
    assert len(prompt) <= 1000


def test_all_evidence_dropped_cannot_leave_a_sufficient_verdict():
    original = _memory()
    result = _bounded_context(original, budget=260)
    assert result["context_epoch"] == 9
    assert result["retrieval"]["status"] == "insufficient"
    assert not result.get("memory_overview")
    assert not result.get("resolution_evidence")
    assert len(_encoded(result)) <= 260


def test_plain_optional_plugin_context_still_has_an_honest_size_boundary():
    assert len(_encoded(_bounded_context({"large": "x" * 1000}, budget=200))) <= 200


def test_profile_budget_keeps_small_view_and_drops_its_removed_binding_text():
    preferences = [f"P{i}" + "偏好" * 30 for i in range(3)]
    original = {"context_epoch": 9, "bond_profile": {
        "character_id": "pet", "stable_preferences": preferences,
        "evidence": {"stable_preferences:" + v: {str(i): "a" * 64} for i, v in enumerate(preferences)}}}
    result = _bounded_context(original, budget=450)
    profile = result["bond_profile"]
    assert 0 < len(profile["stable_preferences"]) < len(preferences)
    assert set(profile["evidence"]) == {"stable_preferences:" + v for v in profile["stable_preferences"]}
    assert len(_encoded(result)) <= 450


def test_service_budget_covers_profile_even_when_query_skips_retrieval(tmp_path):
    from guanghe_companion.emotional_memory_service import EmotionalMemoryService
    from guanghe_companion.retrieval_contract import RetrievalBudget
    memory = EmotionalMemoryService(root=tmp_path, character_id="pet",
                                    retrieval_budget=RetrievalBudget(max_context_chars=512))
    for i in range(4):
        row = memory.remember(kind="用户偏好", title="偏好", summary=f"偏好{i}" + "内容" * 25,
                              source="explicit_user_request", now=i + 1, source_ids=(f"turn:{i}",))
        memory.update_bond_profile(now=i + 1, new_preference=row.summary, source_memory_ids=(row.memory_id,))
    result = memory.retrieve("你好", now=10)
    assert result.trace.status == "not_needed"
    assert result.trace.context_chars <= 512
    assert len(json.dumps(result.bundle.to_prompt_payload(), ensure_ascii=False)) <= 512


def test_trace_reports_evidence_after_context_budget_removes_it(tmp_path):
    from guanghe_companion.emotional_memory_service import EmotionalMemoryService
    from guanghe_companion.retrieval_contract import RetrievalBudget
    memory = EmotionalMemoryService(root=tmp_path, character_id="pet",
                                    retrieval_budget=RetrievalBudget(max_context_chars=700))
    memory.remember(kind="用户偏好", title="姓名", summary="我的名字是小舟。" + "用户本人确认。" * 60,
                    source="explicit_user_request", now=1, source_ids=("turn:1",),
                    metadata={"fact_subject": "user:self", "fact_slot": "姓名", "fact_value": "小舟"})
    result = memory.retrieve("我的名字是什么？", now=2)
    assert result.trace.status == "insufficient"
    assert not result.bundle.memories
    assert result.trace.intent_status == tuple(result.bundle.retrieval.get("intent_status", ()))
