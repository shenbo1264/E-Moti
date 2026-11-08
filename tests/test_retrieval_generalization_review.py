"""Independent source-code review regressions; no holdout data is imported.

The fixtures below are purpose-built counterexamples derived from the public
production contracts: exact object/field identity, current alias evidence,
historical execution versus future applicability, and event occurrence windows.
They use actual SQLite and the production retriever, without embedding mocks.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from guanghe_companion.emotional_memory_service import EmotionalMemoryService


def stamp(month, day, hour=0):
    return int(datetime(2026, month, day, hour, tzinfo=timezone.utc).timestamp())


NOW = stamp(11, 1, 12)


def service(tmp_path):
    # These fixtures explicitly use Unix timestamps; legacy desktop logical
    # seconds must remain incapable of claiming a calendar date association.
    return EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet", time_basis="unix")


def fact(memory, summary, predicate, value, *, subject="user:self", aliases=(), when=NOW - 60, **extra):
    metadata = {"fact_subject": subject, "fact_predicate": predicate, "fact_value": value, **extra}
    if subject.startswith("entity:"):
        metadata["entity_id"] = subject
    if aliases:
        metadata["subject_aliases"] = list(aliases)
    return memory.remember(kind="用户自述", title="来源化记录", summary=summary,
        source="explicit_user_request", source_ids=(f"review:{subject}:{predicate}:{summary}",),
        now=when, valid_from=when, metadata=metadata)


def event(memory, summary, when):
    return memory.remember(kind="共同经历", title="共同观察记录", summary=summary,
        source="local_event", source_ids=(f"review:event:{when}",), now=when,
        metadata={"event_status": "completed", "participants": ["user:self", "character:self"]})


def ids(result):
    return set(result.trace.selected_memory_ids)


def test_open_predicate_does_not_drop_distinguishing_object_qualifier(tmp_path):
    memory = service(tmp_path)
    east = fact(memory, "我的东侧书架高度是120厘米", "furniture_height_custom", "120厘米")
    west = fact(memory, "我的西侧书架高度是180厘米", "furniture_height_custom", "180厘米")
    result = memory.retrieve("我的东侧书架高度是多少？", now=NOW)
    assert east.memory_id in ids(result), result.trace.to_dict()
    assert west.memory_id not in ids(result), result.trace.to_dict()


def test_brand_and_model_remain_distinct_even_in_broad_device_index(tmp_path):
    memory = service(tmp_path)
    brand = fact(memory, "我的扫描仪品牌是VegaForge", "device_brand", "VegaForge", fact_object="扫描仪")
    model = fact(memory, "我的扫描仪型号是QX-7", "device_model", "QX-7", fact_object="扫描仪")
    result = memory.retrieve("我的扫描仪品牌是什么？", now=NOW)
    assert brand.memory_id in ids(result), result.trace.to_dict()
    assert model.memory_id not in ids(result), result.trace.to_dict()


def test_forgetting_nested_subject_never_falls_back_to_its_parent_alias(tmp_path):
    memory = service(tmp_path)
    parent = fact(memory, "顾青的姓名是顾清源", "name", "顾清源",
                  subject="entity:contact_parent", aliases=("顾青",))
    assistant = fact(memory, "顾青的助理的姓名是柳安", "name", "柳安",
                     subject="entity:contact_assistant", aliases=("顾青的助理",))
    question = "顾青的助理的名字是什么？"
    before = memory.retrieve(question, now=NOW)
    assert ids(before) == {assistant.memory_id}, before.trace.to_dict()
    memory.forget(assistant.memory_id, now=NOW + 1)
    after = memory.retrieve(question, now=NOW + 2)
    assert parent.memory_id not in ids(after), after.trace.to_dict()
    assert after.trace.status in {"unknown", "insufficient"}
    assert "柳安" not in after.bundle.to_prompt_text()


def test_minimal_alias_proof_survives_one_revocation_then_stops_after_last(tmp_path):
    memory = service(tmp_path)
    bindings = [fact(memory, f"记录{i}：顾青是这个联系人的称呼", "display_alias", "顾青",
        subject="entity:desk_contact", aliases=("顾青",), when=NOW - 100 + i) for i in range(12)]
    desk = fact(memory, "顾青的工位编号是M-17", "office_desk_identifier_custom", "M-17",
                subject="entity:desk_contact")
    retained = fact(memory, "我的终端重试次数是0", "terminal_retry_limit_custom", 0)
    question = "顾青的工位编号是什么？"
    first = memory.retrieve(question, now=NOW)
    assert ids(first) == {desk.memory_id}, first.trace.to_dict()
    assert len(first.bundle.resolution_evidence) == 1
    chosen = first.bundle.resolution_evidence[0]["memory_id"]
    assert chosen in {entry.memory_id for entry in bindings}
    memory.forget(chosen, now=NOW + 1)
    second = memory.retrieve(question, now=NOW + 2)
    assert ids(second) == {desk.memory_id}, second.trace.to_dict()
    assert len(second.bundle.resolution_evidence) == 1
    assert second.bundle.resolution_evidence[0]["memory_id"] != chosen
    for entry in bindings:
        if entry.memory_id != chosen:
            memory.forget(entry.memory_id, now=NOW + 3)
    after = memory.retrieve(question, now=NOW + 4)
    assert not ids(after), after.trace.to_dict()
    assert desk.memory_id in {e.memory_id for e in memory.store.load_memories() if not e.deleted}
    assert ids(memory.retrieve("我的终端重试次数是多少？", now=NOW + 4)) == {retained.memory_id}


def test_historical_task_does_not_prove_changed_connection_is_applicable(tmp_path):
    memory = service(tmp_path)
    task = memory.remember(kind="任务经验", title="OrchidBridge配对步骤",
        summary="OrchidBridge 2.4之前用USB配对成功，步骤是先开启设备再连接。无线连接仍未验证。",
        source="executor", source_ids=("review:execution:usb-pairing",), now=NOW - 60,
        scope="task_experience", metadata={"app": "OrchidBridge", "version": "2.4",
            "outcome": "succeeded", "preconditions": ["USB连接"], "procedure": "先开启设备再连接"})
    history = memory.retrieve("OrchidBridge 2.4上次USB配对用的步骤是什么？", now=NOW)
    assert task.memory_id in ids(history), history.trace.to_dict()
    current = memory.retrieve("OrchidBridge 2.4之前用USB配对成功，现在改成无线连接还能用原来的步骤吗？", now=NOW)
    assert task.memory_id in ids(current), current.trace.to_dict()
    assert current.trace.status == "insufficient", current.trace.to_dict()
    assert current.trace.intent_status[0]["applicability"] == "requires_current_validation"


def test_episode_date_window_uses_occurrence_not_endless_record_validity(tmp_path):
    memory = service(tmp_path)
    older = event(memory, "我们一起修理收音机，更换了旋钮。", stamp(8, 20))
    asked = event(memory, "我们一起修理收音机，重新焊接了音量电位器。", stamp(9, 10))
    result = memory.retrieve("2026年9月，我们一起修理收音机发生了什么？", now=NOW)
    assert asked.memory_id in ids(result), result.trace.to_dict()
    assert older.memory_id not in ids(result), result.trace.to_dict()


def test_dated_episode_is_found_beyond_recent_candidate_limit(tmp_path):
    memory = service(tmp_path)
    target = event(memory, "我们一起观察云层，完成了一张云图。", stamp(8, 3))
    origin = datetime.fromtimestamp(stamp(8, 4), timezone.utc)
    newer = [replace(target, memory_id=f"review-cloud-{i:03d}",
        occurred_at=int((origin + timedelta(days=i)).timestamp()),
        created_at=int((origin + timedelta(days=i)).timestamp()),
        updated_at=int((origin + timedelta(days=i)).timestamp()),
        source_ids=(f"review:cloud:{i}",)) for i in range(72)]
    memory.store.save_memories((target, *newer))
    result = memory.retrieve("2026年8月3日，我们一起观察云层发生了什么？", now=NOW)
    assert ids(result) == {target.memory_id}, result.trace.to_dict()


def test_open_predicate_zero_and_structured_values_have_literal_evidence(tmp_path):
    memory = service(tmp_path)
    zero = fact(memory, "我的终端重试次数是0", "terminal_retry_limit_custom", 0)
    limits = fact(memory, "我的渲染缓存主限额是4096KB，备选限额是8192KB", "render_cache_limits_custom",
                  {"primary": "4096KB", "fallback": "8192KB"})
    for question, expected in (("我的终端重试次数是多少？", zero), ("我的渲染缓存主限额是多少？", limits)):
        result = memory.retrieve(question, now=NOW)
        assert result.trace.status == "sufficient", result.trace.to_dict()
        assert ids(result) == {expected.memory_id}, result.trace.to_dict()
