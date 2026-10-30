from dataclasses import replace
from pathlib import Path

import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.semantic_memory import SemanticMemoryRetriever


CACHE = Path(__file__).resolve().parents[1] / "artifacts/codex_handoff/embedding-models"


def test_callback_never_loads_model_and_empty_scope_is_empty(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    retriever = SemanticMemoryRetriever(cache_dir=CACHE, character_id="xingxi_pixel_pet", owner_id="local_user")
    try:
        assert retriever("今天吃什么", ()) == {}
        assert retriever.status["model_loaded"] is False
        service.semantic_retriever = retriever
        assert service.recall("今天吃什么", now=100) == ()
    finally:
        retriever.close()


@pytest.fixture(scope="module")
def semantic():
    pytest.importorskip("fastembed")
    if not CACHE.exists() or not tuple(CACHE.rglob("model_optimized.onnx")):
        pytest.skip("run tools/semantic_memory_benchmark.py once to download the real optional model")
    retriever = SemanticMemoryRetriever(cache_dir=CACHE, character_id="xingxi_pixel_pet", owner_id="local_user", local_files_only=True)
    retriever.warmup().result(timeout=90)
    yield retriever
    retriever.close()


def test_real_embedding_prepare_then_service_callback_and_revoke(semantic, tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    memory = service.remember(kind="玩家希望被记住", title="饮食边界", summary="我对花生过敏，不能吃含有花生的食品。", source="explicit_user_request", now=100)
    query = "点餐时应该避开什么食材？"
    semantic.prepare(query, (memory,), now=100).result(timeout=90)
    assert semantic(query, (memory,))[memory.memory_id] > 0
    assert semantic(query, (replace(memory, summary="我喜欢去海边。", version=memory.version + 1),)) == {}
    service.semantic_retriever = semantic
    service.forget(memory.memory_id, now=101)
    assert service.recall(query, now=102) == ()
    semantic.invalidate()
    assert semantic(query, (memory,)) == {}
    future = semantic.prepare(query, (memory,), now=100)
    semantic.invalidate()
    future.result(timeout=90)
    assert semantic(query, (memory,)) == {}


def test_real_embedding_filters_expired_and_other_owner(semantic, tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    memory = service.remember(kind="玩家希望被记住", title="兴趣", summary="我喜欢拍摄飞鸟。", source="explicit_user_request", now=100)
    invalid = (replace(memory, owner_id="other"), replace(memory, memory_id="expired", valid_until=101), replace(memory, memory_id="deleted", deleted=True))
    semantic.prepare("什么事情让我开心", invalid, now=102).result(timeout=90)
    assert semantic("什么事情让我开心", invalid) == {}
