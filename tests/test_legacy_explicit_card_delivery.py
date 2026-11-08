import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.mark.parametrize("title,summary,query", [
    ("用户称呼", "请叫我小榆", "我喜欢什么称呼"),
    ("陶笛练习目标", "我正在练习山间序曲", "陶笛的练习目标"),
    ("favorite mineral", "My favorite mineral is quartz.", "favorite mineral"),
    ("饮品偏好", "我喜欢山楂汽水", "山楂汽水的偏好"),
])
def test_authorized_legacy_card_reaches_evidence_without_external_event_id(tmp_path, title, summary, query):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet")
    saved = service.remember(kind="玩家希望被记住", title=title, summary=summary,
                             source="explicit_user_request", now=1)
    before = saved.metadata.copy()
    result = service.retrieve(query, now=2)
    assert [m.memory_id for m in result.bundle.memories] == [saved.memory_id], result.trace
    assert service.store.load_memories()[0].metadata == before


@pytest.mark.parametrize("title,first,updated,query", [
    ("饮品偏好", "我喜欢红茶", "现在喜欢乌梅茶", "饮品偏好是什么"),
    ("饮品偏好", "我喜欢红茶", "最近只喝杏仁露", "饮品偏好"),
    ("工作城市", "工作城市是秋桐城", "工作城市已改为银杏城", "工作城市是哪"),
])
def test_legacy_correction_uses_current_text_and_explicit_card_context(tmp_path, title, first, updated, query):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet")
    old = service.remember(kind="玩家希望被记住", title=title, summary=first,
                           source="explicit_user_request", now=1)
    new = service.correct(old.memory_id, title=title, summary=updated, now=2)
    result = service.retrieve(query, now=3)
    assert [m.memory_id for m in result.bundle.memories] == [new.memory_id], result.trace
    assert old.memory_id not in [m.memory_id for m in result.bundle.memories]


@pytest.mark.parametrize("summary,source,confirmed,query", [
    ("朋友正在练习山间序曲", "explicit_user_request", True, "我的陶笛练习目标"),
    ("我正在练习山间序曲", "assistant_generated", False, "我的陶笛练习目标"),
    ("我正在练习山间序曲", "explicit_user_request", True, "陶笛的购买价格"),
    ("我正在练习山间序曲", "explicit_user_request", True, "口琴的练习目标"),
    ("我正在练习山间序曲", "explicit_user_request", False, "陶笛的练习目标"),
    ("My favorite mineral is quartz.", "explicit_user_request", True, "favorite color"),
])
def test_legacy_card_must_not_cross_subject_field_or_source(tmp_path, summary, source, confirmed, query):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet")
    service.remember(kind="玩家希望被记住", title="陶笛练习目标", summary=summary,
                      source=source, now=1, user_confirmed=confirmed or source == "assistant_generated")
    assert not service.retrieve(query, now=2).bundle.memories


@pytest.mark.parametrize("query", ["什么是学习目标", "怎样设置练习目标", "如何建立饮品偏好", "工作城市是什么意思"])
def test_field_definition_and_general_advice_do_not_request_personal_memory(tmp_path, query):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet")
    assert service.retrieval_router.plan(query, now=2).routes == ("chat",)
