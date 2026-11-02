from guanghe_companion.emotional_memory_service import EmotionalMemoryService


def test_service_preserves_archive_clock_and_real_change_history(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet", time_basis="unix", timezone_name="UTC")
    entry = service.remember(kind="用户事实", title="住处", summary="用户住在青岛", source="explicit_user_request",
        source_ids=("original",), now=100, occurred_at=80,
        metadata={"fact_subject": "user:self", "fact_predicate": "residence", "fact_slot": "居住地", "fact_domain": "居住地", "fact_value": "青岛"})
    assert entry.occurred_at == 80 and entry.created_at == 100
    changed = service.change(entry.memory_id, title="住处", summary="用户住在大连", now=200, effective_at=180,
        metadata={"fact_subject": "user:self", "fact_predicate": "residence", "fact_slot": "居住地", "fact_domain": "居住地", "fact_value": "大连"})
    restarted = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    assert restarted.time_basis == "unix"
    rows = {e.memory_id: e for e in restarted.store.load_memories()}
    assert rows[entry.memory_id].valid_until == 180 and not rows[entry.memory_id].deleted
    assert rows[changed.memory_id].valid_from == 180
    restarted.forget(changed.memory_id, now=210)
    assert all(e.deleted for e in restarted.store.load_memories())


def test_edit_future_fact_uses_same_management_semantics(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    entry = service.remember(kind="用户事实", title="安排", summary="预定周三学习", source="explicit_user_request",
        source_ids=("plan",), now=10, valid_from=20, metadata={"planned": True})
    fixed = service.correct(entry.memory_id, title="安排", summary="预定周四学习", now=11)
    assert fixed.valid_from == 20


def test_expansion_delivers_only_bound_claim_after_sibling_forgetting(tmp_path):
    from guanghe_companion.memory_source_spans import source_span_metadata
    service = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    text = "我喜欢陶艺，我住在青岛"
    rows = []
    for claim in ("我喜欢陶艺", "我住在青岛"):
        rows.append(service.remember(kind="用户事实", title="事实", summary=claim,
            source="user_chat", source_ids=("utterance:two", claim), now=10,
            metadata={"message_id": "utterance:two", "original_quote": text, **source_span_metadata(text, claim)}))
    service.forget(rows[1].memory_id, now=11)
    result = service.expand_sources({rows[0].memory_id: rows[0].evidence_fingerprint()},
        expected_epoch=service.store.context_epoch, now=11)
    payload = result.bundle.to_prompt_payload()
    assert payload["source_spans"][0]["text"] == "我喜欢陶艺"
    assert "青岛" not in str(payload)


def test_provider_budget_drops_source_span_with_its_fact():
    from guanghe_companion.memory_prompt_budget import trim_memory_evidence
    payload = {"shared_memories": [{"memory_id": "a", "summary": "a fact"}],
        "source_spans": [{"memory_id": "a", "text": "original fact"}],
        "retrieval": {"status": "sufficient"}}
    assert trim_memory_evidence(payload)
    assert not payload.get("source_spans")
