"""Exercise memory ownership through the actual album controller and Qt actions."""

import json
from dataclasses import replace

import pytest

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.memory_album_controller import MemoryAlbumController
from guanghe_companion.memory_album_qt import create_memory_album_widget
from guanghe_companion.memory_album_view_model import build_memory_album


def _album(tmp_path, character_id="xingxi_pixel_pet"):
    story = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id=character_id)
    return story.memory, MemoryAlbumController(story)


def _remember(service, text="我喜欢咖啡", **kwargs):
    return service.remember(kind="玩家希望被记住", title="饮品偏好", summary=text,
                            source="explicit_user_request", now=10, **kwargs)


def _chapter(service, **kwargs):
    first = _remember(service, **kwargs)
    _remember(service, "周末练习电吉他")
    _remember(service, "喜欢安静的早晨")
    chapter = service.consolidate(now=20)
    assert chapter is not None
    return first, chapter


def _cards(snapshot):
    return [card for section in snapshot["sections"] for card in section["cards"]]


def test_album_correction_preserves_event_time_sources_and_increments_version(tmp_path):
    service, album = _album(tmp_path)
    old = _remember(service, source_ids=("message-user-1",), confidence=0.7, valid_until=100)

    album.correct(old.memory_id, title="饮品偏好", summary="我现在更喜欢红茶", now=30)

    active = [row for row in service.store.load_memories() if not row.deleted]
    assert len(active) == 1
    assert active[0].occurred_at == 10
    assert active[0].source_ids == ("message-user-1",)
    assert active[0].version == old.version + 1
    assert active[0].supersedes == old.memory_id
    assert active[0].valid_until == 100


def test_source_details_contains_full_content_and_lifecycle_but_no_raw_metadata(tmp_path):
    service, album = _album(tmp_path)
    full = "这是不能被卡片截断的完整事实。" * 12
    entry = _remember(service, full, source_ids=("user-turn",), confidence=0.7,
                      valid_from=5, valid_until=100, metadata={"raw_text": "不要展示原始观测"})

    details = album.source_details(entry.memory_id)

    assert details["summary"] == full
    assert details["version"] == 1
    assert details["confidence"] == 0.7
    assert details["valid_from"] == 5 and details["valid_until"] == 100
    assert details["source_ids"] == ["user-turn"]
    assert "raw_text" not in json.dumps(details)
    assert "metadata" not in details


def test_source_details_rejects_content_revoked_during_read(tmp_path, monkeypatch):
    service, album = _album(tmp_path)
    entry = _remember(service)
    epoch = service.store.context_epoch
    original_load = type(service.store).load_memories

    def read_then_correct(store):
        rows = original_load(store)
        service.store.upsert_memory(replace(entry, summary="已经纠正的事实", updated_at=20))
        return rows

    monkeypatch.setattr(type(service.store), "load_memories", read_then_correct)

    with pytest.raises(ValueError, match="stale"):
        album.source_details(entry.memory_id, now=20, expected_epoch=epoch)


def test_pending_candidates_have_content_and_confirmation_actions(tmp_path):
    service, album = _album(tmp_path)
    pending = service.propose_explicit_user_memory("请记住：我喜欢红茶", now=10)

    snapshot = album.snapshot()

    assert snapshot["pending_confirmation_count"] == 1
    assert snapshot["pending_candidates"][0]["pending_id"] == pending
    assert snapshot["pending_candidates"][0]["summary"] == "我喜欢红茶"
    assert not service.store.load_memories()
    album.confirm_pending(pending, now=20)
    assert service.store.load_memories()[0].user_confirmed
    second = service.propose_explicit_user_memory("请记住：这项不要保存", now=21)
    album.reject_pending(second)
    assert not service.pending_candidates
    assert len(service.store.load_memories()) == 1


def test_manual_album_input_is_explicitly_proposed_and_confirmed(tmp_path):
    service, album = _album(tmp_path)

    result = album.remember_explicit("我喜欢低频、安静的陪伴。", now=10)

    saved = service.store.load_memories()
    assert len(saved) == 1
    assert saved[0].summary == "我喜欢低频、安静的陪伴。"
    assert saved[0].source == "explicit_user_request"
    assert saved[0].user_confirmed
    assert result["pending_confirmation_count"] == 0


def test_manual_album_input_preserves_all_240_characters(tmp_path):
    service, album = _album(tmp_path)
    content = "我" * 239 + "。"

    album.remember_explicit(content, now=10)

    assert service.store.load_memories()[0].summary == content


def test_manual_album_input_rejects_oversize_without_partial_save(tmp_path):
    service, album = _album(tmp_path)

    with pytest.raises(ValueError):
        album.remember_explicit("我" * 241, now=10)

    assert not service.store.load_memories()
    assert not service.pending_candidates


def test_chapter_cards_only_offer_supported_action(tmp_path):
    service, _ = _album(tmp_path)
    _, chapter = _chapter(service)

    card = build_memory_album((), (chapter,))[0].cards[0]

    assert card.actions == ("查看来源",)


def test_album_and_source_view_hide_chapters_with_expired_evidence(tmp_path):
    service, album = _album(tmp_path)
    _, chapter = _chapter(service, valid_until=25)
    assert chapter.chapter_id in {card["card_id"] for card in _cards(album.snapshot(now=24))}

    assert chapter.chapter_id not in {card["card_id"] for card in _cards(album.snapshot(now=25))}
    with pytest.raises(KeyError):
        album.source_details(chapter.chapter_id, now=25)


@pytest.mark.parametrize("action", ["correct", "pin", "forget", "remember_explicit"])
def test_stale_album_epoch_never_replays_an_edit(tmp_path, action):
    service, album = _album(tmp_path)
    entry = _remember(service)
    unrelated = _remember(service, "周末听音乐")
    epoch = album.snapshot()["context_epoch"]
    service.forget(unrelated.memory_id, now=20)

    with pytest.raises(ValueError, match="stale"):
        if action == "correct":
            album.correct(entry.memory_id, title="饮品", summary="不应写入", now=21, expected_epoch=epoch)
        elif action == "pin":
            album.pin(entry.memory_id, True, now=21, expected_epoch=epoch)
        elif action == "forget":
            album.forget(entry.memory_id, now=21, expected_epoch=epoch)
        else:
            album.remember_explicit("不应写入", now=21, expected_epoch=epoch)

    active = [row for row in service.store.load_memories() if not row.deleted]
    assert [row.summary for row in active] == ["我喜欢咖啡"]
    assert not active[0].pinned


def test_stale_pending_confirmation_is_discarded_without_recreating_forgotten_content(tmp_path):
    service, album = _album(tmp_path)
    entry = _remember(service)
    pending = service.propose_explicit_user_memory("请记住：我喜欢咖啡", now=15)
    service.forget(entry.memory_id, now=20)

    with pytest.raises(ValueError, match="stale"):
        album.confirm_pending(pending, now=21)

    assert not service.recall("咖啡", now=22)
    assert pending not in service.pending_candidates


@pytest.mark.parametrize("action", ["correct", "forget"])
def test_invalidation_between_epoch_check_and_service_commit_rejects_edit(tmp_path, monkeypatch, action):
    service, album = _album(tmp_path)
    target = _remember(service)
    unrelated = _remember(service, "另一条会被遗忘的事实")
    epoch = album.snapshot()["context_epoch"]
    original_action = getattr(service, action)
    original_forget = service.forget

    def invalidate_then_commit(*args, **kwargs):
        original_forget(unrelated.memory_id, now=20)
        return original_action(*args, **kwargs)

    monkeypatch.setattr(service, action, invalidate_then_commit)
    with pytest.raises(ValueError, match="stale"):
        if action == "correct":
            album.correct(target.memory_id, title="偏好", summary="旧编辑不能写入", now=21, expected_epoch=epoch)
        else:
            album.forget(target.memory_id, now=21, expected_epoch=epoch)

    remaining = [row for row in service.store.load_memories() if not row.deleted]
    assert [(row.memory_id, row.summary) for row in remaining] == [(target.memory_id, "我喜欢咖啡")]


def test_invalidating_edits_notify_host_only_after_successful_commit(tmp_path):
    service, initial = _album(tmp_path)
    notices = []
    album = MemoryAlbumController(initial.story, on_invalidated=lambda: notices.append(service.store.context_epoch))
    entry = _remember(service)

    album.correct(entry.memory_id, title="偏好", summary="我喜欢红茶", now=20)
    corrected = next(row for row in service.store.load_memories() if not row.deleted)
    album.forget(corrected.memory_id, now=30)
    assert notices == [1, 2]
    with pytest.raises(KeyError):
        album.correct("missing", title="错误", summary="不应写入", now=40)
    assert notices == [1, 2]


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _select_id(widget, identity):
    from PySide6.QtCore import Qt

    for row in range(widget.memory_list.count()):
        if widget.memory_list.item(row).data(Qt.ItemDataRole.UserRole) == identity:
            widget.memory_list.setCurrentRow(row)
            return
    raise AssertionError(f"card not displayed: {identity}")


def test_qt_correction_starts_from_complete_summary_not_card_preview(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    service, album = _album(tmp_path)
    full = "完整事实不会因为保存纠正而被截断。" * 10
    entry = _remember(service, full)
    widget = create_memory_album_widget(album)
    seen = []
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("更新标题", True))

    def edit(*args, **kwargs):
        seen.append(args[3])
        return args[3], True

    monkeypatch.setattr(QInputDialog, "getMultiLineText", edit)
    _select_id(widget, entry.memory_id)
    widget.memory_action_buttons[1].click()

    assert seen == [full]
    assert next(row for row in service.store.load_memories() if not row.deleted).summary == full
    widget.close()


def test_qt_manual_remember_and_pending_confirm_reject_are_real_actions(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    service, album = _album(tmp_path)
    first = service.propose_explicit_user_memory("请记住：我喜欢红茶", now=10)
    second = service.propose_explicit_user_memory("请记住：不要保存这条", now=11)
    widget = create_memory_album_widget(album)

    _select_id(widget, second)
    widget.memory_pending_buttons[1].click()
    _select_id(widget, first)
    widget.memory_pending_buttons[0].click()
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *args, **kwargs: ("我喜欢电吉他", True))
    widget.memory_remember_button.click()

    saved = service.store.load_memories()
    assert {row.summary for row in saved} == {"我喜欢红茶", "我喜欢电吉他"}
    assert all(row.user_confirmed for row in saved)
    assert not service.pending_candidates
    widget.close()


def test_qt_edit_open_before_forget_does_not_write_back_late_result(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    service, album = _album(tmp_path)
    entry = _remember(service)
    widget = create_memory_album_widget(album)
    notices = []
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("新标题", True))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: notices.append(args[2]))

    def forget_during_edit(*args, **kwargs):
        service.forget(entry.memory_id, now=20)
        return "旧事实不应该回来", True

    monkeypatch.setattr(QInputDialog, "getMultiLineText", forget_during_edit)
    widget.memory_action_buttons[1].click()

    assert notices and "刷新" in notices[0]
    assert not [row for row in service.store.load_memories() if not row.deleted]
    widget.close()


def test_qt_pending_stale_epoch_has_a_refresh_notice(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    service, album = _album(tmp_path)
    entry = _remember(service)
    pending = service.propose_explicit_user_memory("请记住：我喜欢咖啡", now=15)
    service.forget(entry.memory_id, now=20)
    widget = create_memory_album_widget(album)
    notices = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: notices.append(args[2]))

    _select_id(widget, pending)
    widget.memory_pending_buttons[0].click()

    assert notices and "刷新" in notices[0]
    assert not service.recall("咖啡", now=21)
    assert pending not in service.pending_candidates
    widget.close()


def test_qt_character_switch_during_form_never_writes_to_either_character(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    first, first_album = _album(tmp_path, "xingxi_pixel_pet")
    second, second_album = _album(tmp_path, "ikaros_pixel_pet")

    class Host:
        memory_album_controller = first_album

    host = Host()
    widget = create_memory_album_widget(host)
    notices = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: notices.append(args[2]))

    def switch_during_form(*args, **kwargs):
        host.memory_album_controller = second_album
        return "不能跨角色写入", True

    monkeypatch.setattr(QInputDialog, "getMultiLineText", switch_during_form)
    widget.memory_remember_button.click()

    assert notices
    assert not first.store.load_memories()
    assert not second.store.load_memories()
    widget.close()
