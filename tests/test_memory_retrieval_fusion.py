from dataclasses import replace

from guanghe_companion.emotional_memory_service import EmotionalMemoryService


def test_optional_semantic_scores_cannot_bypass_revocation_scope_or_expiry(tmp_path):
    scores = {}
    seen = []
    def provider(query, candidates):
        seen.extend(row.memory_id for row in candidates)
        return scores
    s = EmotionalMemoryService(root=tmp_path, character_id="xingxi", semantic_retriever=provider)
    def remember(summary, **extra):
        return s.remember(kind="玩家希望被记住", title="偏好", summary=summary,
                          source="explicit_user_request", now=1, **extra)
    live = remember("茶")
    old = remember("咖啡")
    work = remember("任务编号", scope="work")
    expired = remember("旧地址", valid_until=5)
    s.forget(old.memory_id, now=2)
    scores.update({live.memory_id: .9, old.memory_id: 1., work.memory_id: 1., expired.memory_id: 1., "unknown":1.})
    recalled = s.recall("beverage", now=10)
    assert [row.memory_id for row in recalled] == [live.memory_id]
    assert set(seen) == {live.memory_id}


def test_semantic_noise_and_provider_failure_fall_back_to_lexical(tmp_path):
    s = EmotionalMemoryService(root=tmp_path, character_id="xingxi",
        semantic_retriever=lambda query, candidates: {row.memory_id: float("nan") for row in candidates})
    fact = s.remember(kind="玩家希望被记住", title="电吉他", summary="每周练习电吉他",
                      source="explicit_user_request", now=1)
    assert not s.recall("astronomy", now=2)
    def broken(query, candidates):
        raise RuntimeError("offline")
    s.semantic_retriever = broken
    assert s.recall("电吉他", now=3)[0].memory_id == fact.memory_id
