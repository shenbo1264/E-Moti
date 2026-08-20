from __future__ import annotations

"""Optional PySide6 renderer for the Starshard Memory Album."""

import json
import time


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
    layout.addWidget(title)
    layout.addWidget(list_widget, stretch=1)
    layout.addWidget(source_view)
    layout.addLayout(actions_layout)
    layout.addWidget(refresh_button)

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

    def refresh() -> None:
        list_widget.clear()
        source_view.clear()
        album = current_album()
        if album is None:
            list_widget.addItem("回忆册尚未接入当前控制器。")
            return
        snapshot = album.snapshot()
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

    def pin_selected() -> None:
        card = selected_card()
        album = current_album()
        if card is None or album is None:
            return
        album.pin(str(card["card_id"]), not bool(card.get("pinned")), now=int(time.time()))
        refresh()
        notify()

    def correct_selected() -> None:
        card = selected_card()
        album = current_album()
        if card is None or album is None:
            return
        title_text, accepted = QInputDialog.getText(widget, "纠正回忆", "标题", text=str(card.get("title", "")))
        if not accepted:
            return
        summary_text, accepted = QInputDialog.getMultiLineText(widget, "纠正回忆", "内容", str(card.get("body", "")))
        if not accepted:
            return
        album.correct(str(card["card_id"]), title=title_text, summary=summary_text, now=int(time.time()))
        refresh()
        notify()

    def forget_selected() -> None:
        card = selected_card()
        album = current_album()
        if card is None or album is None:
            return
        answer = QMessageBox.question(widget, "忘记这段回忆", "确认从回忆册中忘记这段内容？")
        if answer != QMessageBox.StandardButton.Yes:
            return
        album.forget(str(card["card_id"]), now=int(time.time()))
        refresh()
        notify()

    def show_source() -> None:
        card = selected_card()
        album = current_album()
        if card is None or album is None:
            return
        source_view.setPlainText(json.dumps(album.source_details(str(card["card_id"])), ensure_ascii=False, indent=2))
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
    refresh()
    widget.memory_list = list_widget  # type: ignore[attr-defined]
    widget.memory_source_view = source_view  # type: ignore[attr-defined]
    widget.memory_action_buttons = action_buttons  # type: ignore[attr-defined]
    widget.refresh_memory_album = refresh  # type: ignore[attr-defined]
    return widget
