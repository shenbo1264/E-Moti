from __future__ import annotations

"""Optional PySide6 renderer for the Starshard Memory Album."""

import time

from .memory_album_controller import MemoryAlbumStaleError
from .memory_settings_view_model import source_details_text


def create_memory_album_widget(controller: object, on_changed=None, parent: object | None = None):
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QInputDialog,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPushButton,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PySide6 is required for the memory album widget") from exc
    if QApplication.instance() is None:
        raise RuntimeError("PySide6 QApplication is required for the memory album widget")

    def current_album():
        album = controller if callable(getattr(controller, "snapshot", None)) else getattr(controller, "memory_album_controller", None)
        if album is None:
            story = getattr(controller, "story_runtime", None) or getattr(controller, "story", None)
            if story is not None:
                from .memory_album_controller import MemoryAlbumController
                album = MemoryAlbumController(story)
        return album

    if current_album() is None:
        raise RuntimeError("PySide6 memory album widget requires a compatible controller")

    widget = QWidget(parent)
    layout = QVBoxLayout(widget)
    title = QLabel("星屑回忆册")
    title.setAlignment(Qt.AlignmentFlag.AlignLeft)
    remember_button = QPushButton("记住一件事")
    heading_layout = QHBoxLayout()
    heading_layout.addWidget(title, stretch=1)
    heading_layout.addWidget(remember_button)
    pending_status = QLabel()
    list_widget = QListWidget()
    source_view = QTextEdit()
    source_view.setReadOnly(True)
    source_view.setMaximumHeight(120)
    source_view.setPlaceholderText("选择一条回忆后可查看来源。")
    refresh_button = QPushButton("刷新回忆")
    actions_layout = QHBoxLayout()
    pin_button = QPushButton("固定")
    correct_button = QPushButton("纠正")
    forget_button = QPushButton("忘记")
    source_button = QPushButton("查看来源")
    action_buttons = (pin_button, correct_button, forget_button, source_button)
    for button in action_buttons:
        actions_layout.addWidget(button)
    pending_layout = QHBoxLayout()
    confirm_button = QPushButton("确认记住")
    reject_button = QPushButton("不记住")
    pending_buttons = (confirm_button, reject_button)
    for button in pending_buttons:
        pending_layout.addWidget(button)
    pending_layout.addStretch()
    layout.addLayout(heading_layout)
    layout.addWidget(pending_status)
    layout.addWidget(list_widget, stretch=1)
    layout.addLayout(pending_layout)
    layout.addWidget(source_view)
    layout.addLayout(actions_layout)
    layout.addWidget(refresh_button)
    displayed_album = None
    displayed_epoch = None

    def selected_card() -> dict[str, object] | None:
        item = list_widget.currentItem()
        payload = item.data(Qt.ItemDataRole.UserRole + 1) if item else None
        return payload if isinstance(payload, dict) else None

    def update_actions() -> None:
        card = selected_card()
        allowed = set(card.get("actions", [])) if card else set()
        pin_button.setEnabled("固定" in allowed)
        correct_button.setEnabled("纠正" in allowed)
        forget_button.setEnabled("忘记" in allowed)
        source_button.setEnabled(card is not None)
        pin_button.setText("取消固定" if card and card.get("pinned") else "固定")
        for button in pending_buttons:
            button.setEnabled(bool(card and card.get("pending")))

    def refresh() -> None:
        nonlocal displayed_album, displayed_epoch
        list_widget.clear()
        source_view.clear()
        displayed_album = None
        displayed_epoch = None
        album = current_album()
        if album is None:
            list_widget.addItem("回忆册尚未接入当前控制器。")
            pending_status.setText("")
            update_actions()
            return
        try:
            snapshot = album.snapshot()
        except MemoryAlbumStaleError:
            pending_status.setText("回忆正在更新，请稍后刷新。")
            update_actions()
            return
        displayed_album = album
        displayed_epoch = snapshot["context_epoch"]
        pending = snapshot.get("pending_candidates", [])
        pending_status.setText(f"待确认 {len(pending)} 条 · 只有确认后才会长期记住。" if pending else "你可以添加、纠正或忘记自己的回忆。")
        if pending:
            header = QListWidgetItem("【等待你的确认】")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            list_widget.addItem(header)
            for candidate in pending:
                card = dict(candidate, card_id=candidate["pending_id"], pending=True, actions=[])
                item = QListWidgetItem(f"{card.get('title', '')}\n{card.get('summary', '')}")
                item.setData(Qt.ItemDataRole.UserRole, card["card_id"])
                item.setData(Qt.ItemDataRole.UserRole + 1, card)
                list_widget.addItem(item)
        for section in snapshot.get("sections", []):
            category = str(section.get("category", ""))
            header = QListWidgetItem(f"【{category}】")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            list_widget.addItem(header)
            for card in section.get("cards", []):
                item = QListWidgetItem(f"{card.get('title', '')}\n{card.get('body', '')}")
                item.setData(Qt.ItemDataRole.UserRole, card.get("card_id", ""))
                item.setData(Qt.ItemDataRole.UserRole + 1, dict(card))
                list_widget.addItem(item)
        if list_widget.count() > 1:
            list_widget.setCurrentRow(1)
        update_actions()

    def notify() -> None:
        if callable(on_changed):
            on_changed()

    def edit_context():
        album = current_album()
        if album is None or displayed_album is None or album.story.memory is not displayed_album.story.memory:
            raise MemoryAlbumStaleError("character or memory album changed; refresh")
        return album, displayed_epoch

    def check_character(album) -> None:
        current = current_album()
        if current is None or current.story.memory is not album.story.memory:
            raise MemoryAlbumStaleError("character changed while editing; refresh")

    def show_error(exc: Exception) -> None:
        if isinstance(exc, (KeyError, MemoryAlbumStaleError)) or "stale" in str(exc):
            refresh()
            QMessageBox.information(widget, "回忆已更新", "内容或角色已发生变化，已刷新回忆册。不会自动重新提交刚才的输入，请检查后重新操作。")
        else:
            QMessageBox.information(widget, "请检查回忆内容", "内容不能为空，最多 240 字；标题最多 60 字。")

    def pin_selected() -> None:
        card = selected_card()
        if card is None:
            return
        try:
            album, epoch = edit_context()
            album.pin(str(card["card_id"]), not bool(card.get("pinned")), now=int(time.time()), expected_epoch=epoch)
        except (KeyError, ValueError) as exc:
            show_error(exc)
            return
        refresh()
        notify()

    def correct_selected() -> None:
        card = selected_card()
        if card is None:
            return
        try:
            album, epoch = edit_context()
            details = album.source_details(str(card["card_id"]), expected_epoch=epoch)
            title_text, accepted = QInputDialog.getText(widget, "纠正回忆", "标题（最多 60 字）", text=str(details["title"]))
            if not accepted:
                return
            check_character(album)
            summary_text, accepted = QInputDialog.getMultiLineText(widget, "纠正回忆", "完整内容（最多 240 字）", str(details["summary"]))
            if not accepted:
                return
            check_character(album)
            album.correct(str(card["card_id"]), title=title_text, summary=summary_text, now=int(time.time()), expected_epoch=epoch)
        except (KeyError, ValueError) as exc:
            show_error(exc)
            return
        refresh()
        notify()

    def forget_selected() -> None:
        card = selected_card()
        if card is None:
            return
        try:
            album, epoch = edit_context()
            answer = QMessageBox.question(widget, "忘记这段回忆", "确认从回忆册中忘记这段内容？")
            if answer != QMessageBox.StandardButton.Yes:
                return
            check_character(album)
            album.forget(str(card["card_id"]), now=int(time.time()), expected_epoch=epoch)
        except (KeyError, ValueError) as exc:
            show_error(exc)
            return
        refresh()
        notify()

    def remember_explicit() -> None:
        try:
            album, epoch = edit_context()
            text, accepted = QInputDialog.getMultiLineText(widget, "记住一件事", "你希望长期记住的内容（最多 240 字；确认后保存）", "")
            if not accepted:
                return
            check_character(album)
            album.remember_explicit(text, now=int(time.time()), expected_epoch=epoch)
        except (KeyError, ValueError) as exc:
            show_error(exc)
            return
        refresh()
        notify()

    def resolve_pending(confirmed: bool) -> None:
        card = selected_card()
        if card is None or not card.get("pending"):
            return
        try:
            album, epoch = edit_context()
            pending_id = str(card["pending_id"])
            if confirmed:
                album.confirm_pending(pending_id, now=int(time.time()), expected_epoch=epoch)
            else:
                album.reject_pending(pending_id, expected_epoch=epoch)
        except (KeyError, ValueError) as exc:
            show_error(exc)
            return
        refresh()
        notify()

    def show_source() -> None:
        card = selected_card()
        if card is None:
            return
        try:
            album, epoch = edit_context()
            if card.get("pending"):
                if epoch != album.story.memory.store.context_epoch:
                    raise MemoryAlbumStaleError("stale pending memory; refresh")
                details = {key: card[key] for key in ("pending_id", "summary", "source", "source_ids", "occurred_at")}
            else:
                details = album.source_details(str(card["card_id"]), expected_epoch=epoch)
            source_view.setPlainText(source_details_text(details))
        except (KeyError, ValueError) as exc:
            show_error(exc)

    def refresh_and_notify() -> None:
        refresh()
        if callable(on_changed):
            on_changed()
    refresh_button.clicked.connect(refresh_and_notify)
    list_widget.currentItemChanged.connect(update_actions)
    pin_button.clicked.connect(pin_selected)
    correct_button.clicked.connect(correct_selected)
    forget_button.clicked.connect(forget_selected)
    source_button.clicked.connect(show_source)
    remember_button.clicked.connect(remember_explicit)
    confirm_button.clicked.connect(lambda: resolve_pending(True))
    reject_button.clicked.connect(lambda: resolve_pending(False))
    refresh()
    widget.memory_list = list_widget  # type: ignore[attr-defined]
    widget.memory_source_view = source_view  # type: ignore[attr-defined]
    widget.memory_action_buttons = action_buttons  # type: ignore[attr-defined]
    widget.memory_pending_buttons = pending_buttons  # type: ignore[attr-defined]
    widget.memory_remember_button = remember_button  # type: ignore[attr-defined]
    widget.refresh_memory_album = refresh  # type: ignore[attr-defined]
    return widget
