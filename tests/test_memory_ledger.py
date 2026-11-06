"""The album explains what is remembered, why, and until when."""

import json

import pytest

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.memory_album_controller import MemoryAlbumController, MemoryAlbumStaleError
from guanghe_companion.memory_evidence_view_model import present_evidence
from guanghe_companion.memory_ledger_view_model import build_memory_ledger, time_label


def _album(tmp_path, clock=None):
    story = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi_pixel_pet")
    return story.memory, MemoryAlbumController(story, clock=clock)


def _fact(service, summary="用户喜欢乌龙茶", **kwargs):
    kwargs.setdefault("metadata", {"fact_subject": "user:self", "fact_slot": "preference:drink"})
    kwargs.setdefault("now", 100)
    return service.remember(kind="玩家希望被记住", title="饮品偏好", summary=summary,
                            source="explicit_user_request", **kwargs)


def _section(snapshot, key):
    return next(row for row in snapshot["ledger"] if row["key"] == key)


def test_ledger_separates_every_memory_state(tmp_path):
    service, album = _album(tmp_path)
    _fact(service)
    _fact(service, "用户以前住在苏州", valid_until=150)
    service.remember(kind="日常", title="周末计划", summary="周六一起看展", source="user_chat", now=100,
                     metadata={"plan_status": "planned"})
    service.remember(kind="共同学习", title="一起学吉他", summary="今天第一次一起练琴", source="game_event", now=100)
    service.remember(kind="任务", title="导出备份", summary="导出成功", source="trusted_executor", now=100,
                     scope="task_experience", metadata={"outcome": "succeeded"})

    snapshot = album.snapshot(now=200)

    assert [c["title"] for c in _section(snapshot, "fact")["cards"]] == ["饮品偏好"]
    assert [c["body"] for c in _section(snapshot, "history")["cards"]] == ["用户以前住在苏州"]
    assert [c["title"] for c in _section(snapshot, "plan")["cards"]] == ["周末计划"]
    assert [c["title"] for c in _section(snapshot, "episode")["cards"]] == ["一起学吉他"]
    assert [c["title"] for c in _section(snapshot, "task")["cards"]] == ["导出备份"]
    assert _section(snapshot, "external")["cards"] == []
    assert "不保存" in _section(snapshot, "external")["hint"]


def test_card_shows_subject_field_source_time_version_scope_and_status(tmp_path):
    service, album = _album(tmp_path)
    _fact(service, valid_until=500)

    card = _section(album.snapshot(now=200), "fact")["cards"][0]

    assert card["subject"] == "你"
    assert card["field"] == "偏好 · drink"
    assert card["source_label"] == "你亲口要求记住"
    assert card["version"] == 1
    assert card["scope_label"] == "陪伴"
    assert card["status_label"] == "当前有效"
    assert "到" in card["valid_label"]


def test_logical_time_never_becomes_a_calendar_date():
    assert time_label(90_000, "logical") == "相处第 2 天（逻辑时间）"
    assert time_label(2_000_000_000, "logical") != "2033-05-18"
    assert "1970" not in time_label(1000, "logical")
    assert time_label(0, "logical") == "未记录"
    assert time_label(1_793_000_000, "unix", "Asia/Shanghai").startswith("2026-")


def test_forgotten_and_corrected_records_keep_no_old_text(tmp_path):
    service, album = _album(tmp_path)
    forgotten = _fact(service, "用户的秘密是橙色猫")
    corrected = _fact(service, "用户住在杭州")
    service.forget(forgotten.memory_id, now=120)
    service.correct(corrected.memory_id, title="住址", summary="用户住在南京", now=130)

    snapshot = album.snapshot(now=200)
    retired = _section(snapshot, "retired")["cards"]
    text = json.dumps(retired, ensure_ascii=False)

    assert "橙色猫" not in text and "杭州" not in text
    assert {c["status_label"] for c in retired} == {"已忘记", "已更正"}
    assert next(c for c in retired if c["status_label"] == "已忘记")["actions"] == ["彻底删除"]
    assert next(c for c in retired if c["status_label"] == "已更正")["actions"] == []
    assert [c["body"] for c in _section(snapshot, "fact")["cards"]] == ["用户住在南京"]


def test_old_body_is_absent_from_ledger_cards_after_purge(tmp_path):
    service, album = _album(tmp_path)
    entry = _fact(service, "用户的秘密是橙色猫")
    epoch = service.store.context_epoch

    snapshot = album.purge(entry.memory_id, now=150, expected_epoch=epoch)

    assert "橙色猫" not in json.dumps(snapshot, ensure_ascii=False)
    assert "橙色猫" not in json.dumps([row.to_dict() for row in service.store.load_memories()], ensure_ascii=False)


def test_reality_change_moves_old_fact_to_history(tmp_path):
    service, album = _album(tmp_path)
    entry = _fact(service, "用户住在杭州")

    snapshot = album.change(entry.memory_id, title="住址", summary="用户搬到了南京", now=300,
                            expected_epoch=service.store.context_epoch)

    assert [c["body"] for c in _section(snapshot, "fact")["cards"]] == ["用户搬到了南京"]
    assert [c["body"] for c in _section(snapshot, "history")["cards"]] == ["用户住在杭州"]


def test_change_with_stale_epoch_is_refused_and_keeps_fact(tmp_path):
    service, album = _album(tmp_path)
    entry = _fact(service)
    with pytest.raises(MemoryAlbumStaleError):
        album.change(entry.memory_id, title="x", summary="y", now=300, expected_epoch=-1)
    assert service.store.load_memories()[0].summary == "用户喜欢乌龙茶"


def test_album_writes_use_host_clock_not_wall_clock(tmp_path):
    service, album = _album(tmp_path, clock=lambda: 777)
    entry = _fact(service)

    album.pin(entry.memory_id, True, expected_epoch=service.store.context_epoch)

    assert service.store.load_memories()[0].updated_at == 777
    assert album.current_time() == 777


def test_ask_returns_sourced_claims_and_expand_uses_fingerprint(tmp_path):
    service, album = _album(tmp_path)
    entry = _fact(service, "我喜欢喝乌龙茶", metadata={})

    asked = album.ask("我喜欢喝什么", now=200)

    assert asked["status"] == "sufficient"
    claim = next(c for c in asked["claims"] if c["memory_id"] == entry.memory_id)
    assert claim["fingerprint"] == entry.evidence_fingerprint()
    expanded = album.expand({claim["memory_id"]: claim["fingerprint"]},
                            expected_epoch=asked["context_epoch"], now=200)
    assert expanded["status"] == "sufficient"
    assert [card["summary"] for card in expanded["cards"]] == ["我喜欢喝乌龙茶"]
    assert "完整聊天原文" in expanded["note"]


def test_expand_after_forget_is_unavailable_and_returns_no_old_text(tmp_path):
    service, album = _album(tmp_path)
    entry = _fact(service, "我喜欢喝乌龙茶", metadata={})
    asked = album.ask("我喜欢喝什么", now=200)
    claim = asked["claims"][0]
    service.forget(entry.memory_id, now=210)

    expanded = album.expand({claim["memory_id"]: claim["fingerprint"]},
                            expected_epoch=asked["context_epoch"], now=220)

    assert expanded["status"] == "unavailable"
    assert expanded["cards"] == []
    assert "乌龙茶" not in json.dumps(expanded, ensure_ascii=False)


def test_ask_does_not_replace_the_turn_trace(tmp_path):
    service, album = _album(tmp_path)
    _fact(service, "我喜欢喝乌龙茶", metadata={})
    marker = object()
    service.last_retrieval_trace = marker
    album.ask("我喜欢喝什么", now=200)
    assert service.last_retrieval_trace is marker


def test_turn_evidence_reports_status_and_invalidates_after_epoch_change(tmp_path):
    service, album = _album(tmp_path)
    entry = _fact(service, "我喜欢喝乌龙茶", metadata={})
    service.retrieve("我喜欢喝什么", now=200)
    album.capture_turn_evidence()
    service.retrieve("", now=200)

    turn = album.turn_evidence(now=200)
    assert turn["status"] == "sufficient"
    assert turn["claims"][0]["memory_id"] == entry.memory_id

    service.forget(entry.memory_id, now=210)
    turn = album.turn_evidence(now=220)
    assert turn["status"] == "unavailable"
    assert turn["claims"] == []


@pytest.mark.parametrize("status", ["sufficient", "insufficient", "unknown", "external_unavailable", "unavailable"])
def test_no_evidence_state_is_an_error(status):
    view = present_evidence(status)
    assert view["tone"] != "danger"
    assert view["label"] and view["detail"]


def test_not_needed_is_silent_and_unknown_never_blames_the_user():
    assert present_evidence("not_needed") is None
    unknown = present_evidence("unknown")
    assert "没说过" in unknown["detail"] and "不代表" in unknown["detail"]
    assert "重新" not in unknown["detail"]


def test_insufficient_names_what_is_missing():
    view = present_evidence("insufficient", missing=("原因",))
    assert "原因" in view["detail"]
    assert "确认" not in view["label"]
