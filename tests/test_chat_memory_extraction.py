import pytest

from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, MemoryProposal, should_extract
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


@pytest.fixture
def extraction(tmp_path):
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    return ChatMemoryExtraction(memory)


def proposal(**changes):
    values = dict(action="remember", quote="我的常用称呼是小羽", value="小羽", predicate="name",
                  domain="称呼", target_ids=(), certainty="explicit", scene="personal")
    return MemoryProposal(**(values | changes))


def test_trusted_input_commits_literal_fact_once(extraction):
    envelope = extraction.prepare("我的常用称呼是小羽", now=10, mode="auto", generation=2)
    result = extraction.apply(envelope, (proposal(),), now=11, mode="auto", generation=2)
    assert result.status == "saved"
    entry = extraction.memory.store.load_memories()[0]
    assert "小羽" in entry.summary and entry.metadata["original_quote"] == envelope.text
    with pytest.raises(ValueError):
        extraction.apply(envelope, (proposal(),), now=12, mode="auto", generation=2)


@pytest.mark.parametrize("text", ["如果我的常用称呼是小羽", "朋友说我的常用称呼是小羽", "游戏里我的常用称呼是小羽", "我的称呼是什么？"])
def test_untrusted_semantics_cannot_become_fact(extraction, text):
    assert not should_extract(text)
    envelope = extraction.prepare(text, now=10, mode="auto", generation=0)
    assert extraction.apply(envelope, (proposal(),), now=11, mode="auto", generation=0).status == "ignored"
    assert not extraction.memory.store.load_memories()


@pytest.mark.parametrize("changes", [{"value": "小云"}, {"quote": "我叫小羽"}, {"domain": "管理权限"}, {"target_ids": ("unknown",)}])
def test_invalid_model_output_is_rejected(extraction, changes):
    envelope = extraction.prepare("我的常用称呼是小羽", now=10, mode="auto", generation=0)
    with pytest.raises(ValueError):
        extraction.apply(envelope, (proposal(**changes),), now=11, mode="auto", generation=0)


def test_changed_epoch_mode_or_generation_rejects_late_result(extraction):
    for field in ("mode", "generation"):
        envelope = extraction.prepare("我的常用称呼是小羽", now=10, mode="auto", generation=0)
        args = {"mode": "auto", "generation": 0, field: "off" if field == "mode" else 1}
        with pytest.raises(ValueError):
            extraction.apply(envelope, (proposal(),), now=11, **args)


def test_review_candidate_uses_existing_pending_store(extraction):
    envelope = extraction.prepare("我的常用称呼是小羽", now=10, mode="review", generation=0)
    assert extraction.apply(envelope, (proposal(),), now=11, mode="review", generation=0).status == "pending"
    assert not extraction.memory.store.load_memories()
    assert len(extraction.memory.pending_candidates) == 1


def test_correction_then_forget_revokes_existing_fact(extraction):
    old = extraction.memory.remember(kind="用户自述", title="称呼", summary="用户希望被称呼为小羽",
        source="explicit_user_request", now=1, source_ids=("old-user-turn",))
    envelope = extraction.prepare("更正一下，我的称呼是小澈", now=10, mode="auto", generation=0)
    changed = proposal(action="correct", quote=envelope.text, value="小澈", target_ids=(old.memory_id,))
    assert extraction.apply(envelope, (changed,), now=11, mode="auto", generation=0).status == "saved"
    active = [m for m in extraction.memory.store.load_memories() if not m.deleted]
    assert len(active) == 1 and "小澈" in active[0].summary
    envelope = extraction.prepare("请忘掉小澈这个称呼", now=12, mode="auto", generation=0)
    forgotten = proposal(action="forget", quote=envelope.text, value="小澈", target_ids=(active[0].memory_id,))
    assert extraction.apply(envelope, (forgotten,), now=13, mode="auto", generation=0).status == "forgotten"
    assert not [m for m in extraction.memory.store.load_memories() if not m.deleted]


def test_negation_cannot_be_relabelled_as_positive_allergy(extraction):
    envelope = extraction.prepare("我对核桃不过敏", now=10, mode="auto", generation=0)
    with pytest.raises(ValueError):
        extraction.apply(envelope, (proposal(quote=envelope.text, value="核桃", predicate="allergy", domain="过敏"),),
                         now=11, mode="auto", generation=0)


def test_host_detects_conflict_without_model_target(extraction):
    old = extraction.memory.remember(kind="用户自述", title="居住地", summary="我住在宁波",
        source="explicit_user_request", now=1, source_ids=("old",))
    envelope = extraction.prepare("我的常住地址在泉州", now=10, mode="auto", generation=0)
    p = proposal(quote=envelope.text, value="泉州", predicate="residence", domain="居住地")
    assert extraction.apply(envelope, (p,), now=11, mode="auto", generation=0).status == "pending"
    pending = next(iter(extraction.memory.pending_candidates.values()))
    assert pending.metadata["supersedes_memory_id"] == old.memory_id


def test_domain_forget_with_empty_value_is_available_when_off(extraction):
    old = extraction.memory.remember(kind="用户自述", title="居住地", summary="我住在宁波",
        source="explicit_user_request", now=1, source_ids=("old",))
    assert should_extract("忘掉我的住址", mode="off")
    assert not should_extract("我的名字是小羽", mode="off")
    envelope = extraction.prepare("忘掉我的住址", now=10, mode="off", generation=0)
    p = proposal(action="forget", quote=envelope.text, value="", predicate="residence", domain="居住地",
                 target_ids=(old.memory_id,))
    assert extraction.apply(envelope, (p,), now=11, mode="off", generation=0).status == "forgotten"
