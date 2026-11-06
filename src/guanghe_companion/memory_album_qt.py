from __future__ import annotations

"""Optional PySide6 renderer for the Starshard Memory Album."""

import sqlite3

from .memory_album_controller import MemoryAlbumStaleError
from .memory_edit_session import EDIT_INTENTS, MemoryEditSession, save_failure_reason
from .memory_settings_view_model import ledger_card_details, ledger_card_text, source_details_text

PURGE_WARNING = ("这会从记忆中移除这条内容和它的全部版本，之后无法恢复。\n"
                 "存档里只留下不含正文的编号，防止它被重新写回。\n"
                 "已有的存档备份和 SQLite 文件的旧页不在此范围内。")


def create_memory_album_widget(controller: object, on_changed=None, parent: object | None = None):
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QButtonGroup,
            QDialog,
            QDialogButtonBox,
            QHBoxLayout,
            QInputDialog,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPushButton,
            QRadioButton,
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
    title.setProperty("role", "section")
    title.setAlignment(Qt.AlignmentFlag.AlignLeft)
    remember_button = QPushButton("记住一件事")
    remember_button.setProperty("role", "primary")
    heading_layout = QHBoxLayout()
    heading_layout.addWidget(title, stretch=1)
    heading_layout.addWidget(remember_button)
    pending_status = QLabel()
    pending_status.setProperty("role", "secondary")
    pending_status.setWordWrap(True)
    ask_layout = QHBoxLayout()
    ask_input = QLineEdit()
    ask_input.setPlaceholderText("问问它记得什么，比如：我喜欢喝什么")
    ask_input.setAccessibleName("在回忆里查找")
    ask_button = QPushButton("查找")
    ask_layout.addWidget(ask_input, stretch=1)
    ask_layout.addWidget(ask_button)
    evidence_label = QLabel()
    evidence_label.setProperty("role", "status")
    evidence_label.setWordWrap(True)
    evidence_label.setAccessibleName("这次的记忆依据状态")
    evidence_label.hide()
    claim_list = QListWidget()
    claim_list.setAccessibleName("有来源的记忆概览")
    claim_list.setWordWrap(True)
    claim_list.setMaximumHeight(110)
    claim_list.hide()
    list_widget = QListWidget()
    list_widget.setAccessibleName("回忆列表")
    list_widget.setWordWrap(True)
    list_widget.setMinimumHeight(280)
    list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    source_view = QTextEdit()
    source_view.setReadOnly(True)
    source_view.setMinimumHeight(96)
    source_view.setMaximumHeight(180)
    source_view.setAccessibleName("回忆来源与原文")
    source_view.setPlaceholderText("选择一条回忆后可查看来源。")
    refresh_button = QPushButton("刷新回忆")
    heading_layout.addWidget(refresh_button)
    actions_layout = QHBoxLayout()
    pin_button = QPushButton("固定")
    correct_button = QPushButton("修改")
    forget_button = QPushButton("忘记")
    forget_button.setToolTip("不再使用这条记忆。正文还在本机存档，之后可以彻底删除。")
    purge_button = QPushButton("彻底删除")
    purge_button.setProperty("role", "danger")
    source_button = QPushButton("查看来源")
    action_buttons = (pin_button, correct_button, forget_button, source_button, purge_button)
    for button in action_buttons:
        actions_layout.addWidget(button)
    pending_layout = QHBoxLayout()
    confirm_button = QPushButton("确认记住")
    confirm_button.setProperty("role", "primary")
    reject_button = QPushButton("不记住")
    pending_buttons = (confirm_button, reject_button)
    for button in pending_buttons:
        pending_layout.addWidget(button)
    pending_layout.addStretch()
    layout.addLayout(heading_layout)
    layout.addWidget(pending_status)
    layout.addLayout(ask_layout)
    layout.addWidget(evidence_label)
    layout.addWidget(claim_list)
    layout.addWidget(list_widget, stretch=1)
    layout.addLayout(pending_layout)
    source_label = QLabel("来源与原文")
    source_label.setBuddy(source_view)
    layout.addWidget(source_label)
    layout.addWidget(source_view)
    layout.addLayout(actions_layout)
    displayed_album = None
    displayed_epoch = None
    displayed_character = ""
    claims_epoch = None
    open_edit: dict[str, object] = {}

    def selected_card() -> dict[str, object] | None:
        item = list_widget.currentItem()
        payload = item.data(Qt.ItemDataRole.UserRole + 1) if item else None
        return payload if isinstance(payload, dict) else None

    def update_actions() -> None:
        card = selected_card()
        allowed = set(card.get("actions", [])) if card else set()
        pin_button.setEnabled("固定" in allowed)
        correct_button.setEnabled("修改" in allowed)
        forget_button.setEnabled("忘记" in allowed)
        purge_button.setEnabled("彻底删除" in allowed)
        source_button.setEnabled(card is not None and card.get("section") != "retired")
        pin_button.setText("取消固定" if card and card.get("pinned") else "固定")
        for button in pending_buttons:
            button.setEnabled(bool(card and card.get("pending")))

    def clear_claims() -> None:
        nonlocal claims_epoch
        claims_epoch = None
        claim_list.clear()
        claim_list.hide()
        evidence_label.clear()
        evidence_label.hide()

    def refresh() -> None:
        nonlocal displayed_album, displayed_epoch, displayed_character
        list_widget.clear()
        source_view.clear()
        displayed_album = None
        displayed_epoch = None
        album = current_album()
        if album is None:
            clear_claims()
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
        if snapshot.get("character_id") != displayed_character or claims_epoch != displayed_epoch:
            # 概览是某一版本的缓存：版本或角色一变就整体清掉，不让旧内容留在屏幕上。
            clear_claims()
        displayed_character = str(snapshot.get("character_id", ""))
        ledger = snapshot.get("ledger", [])
        pending = snapshot.get("pending_candidates", [])
        pending_status.setText(f"待确认 {len(pending)} 条 · 只有确认后才会长期记住。" if pending else "你可以添加、修改或忘记自己的回忆。")
        live_ids = set()
        external_hint = ""
        for section in ledger:
            if section["key"] == "external":
                external_hint = str(section["hint"])
            cards = section.get("cards", [])
            if not cards:
                continue
            header = QListWidgetItem(f"【{section['label']}】{section['hint']}")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            list_widget.addItem(header)
            for card in cards:
                if section["key"] not in {"retired", "pending"}:
                    live_ids.add(str(card["card_id"]))
                item = QListWidgetItem(ledger_card_text(card))
                item.setData(Qt.ItemDataRole.UserRole, card.get("card_id", ""))
                item.setData(Qt.ItemDataRole.UserRole + 1, dict(card))
                list_widget.addItem(item)
        if list_widget.count() > 1:
            list_widget.setCurrentRow(1)
        elif list_widget.count() == 0:
            empty = QListWidgetItem("还没有回忆。可以从普通聊天开始，也可以选择“记住一件事”。")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            list_widget.addItem(empty)
        external_row = QListWidgetItem(f"【外部实时状态】{external_hint}")
        external_row.setFlags(Qt.ItemFlag.NoItemFlags)
        if external_hint and list_widget.count() and selected_card() is not None:
            list_widget.addItem(external_row)
        sync_open_edit(live_ids)
        update_actions()

    def sync_open_edit(live_ids: set[str]) -> None:
        session = open_edit.get("session")
        if session is None:
            return
        session.on_album_changed(character_id=displayed_character, epoch=displayed_epoch, live_ids=live_ids)
        open_edit["sync"]()

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
            QMessageBox.information(widget, "没有保存", save_failure_reason(exc) + "。")

    def pin_selected() -> None:
        card = selected_card()
        if card is None:
            return
        try:
            album, epoch = edit_context()
            album.pin(str(card["card_id"]), not bool(card.get("pinned")), expected_epoch=epoch)
        except (KeyError, ValueError) as exc:
            show_error(exc)
            return
        refresh()
        notify()

    def edit_selected() -> None:
        card = selected_card()
        if card is None:
            return
        try:
            album, epoch = edit_context()
            details = album.source_details(str(card["card_id"]), expected_epoch=epoch)
        except (KeyError, ValueError) as exc:
            show_error(exc)
            return
        session = MemoryEditSession(str(card["card_id"]), displayed_character, epoch,
                                    str(details["title"]), str(details["summary"]))
        dialog = QDialog(widget)
        dialog.setWindowTitle("修改这条记忆")
        box = QVBoxLayout(dialog)
        group = QButtonGroup(dialog)
        radios = {}
        for index, (key, label, hint) in enumerate(EDIT_INTENTS):
            radio = QRadioButton(f"{label}：{hint}")
            radio.setChecked(index == 0)
            group.addButton(radio)
            radios[key] = radio
            box.addWidget(radio)
        title_input = QLineEdit(session.title)
        title_input.setAccessibleName("记忆标题")
        summary_input = QTextEdit()
        summary_input.setPlainText(session.summary)
        summary_input.setAccessibleName("记忆内容")
        notice = QLabel()
        notice.setWordWrap(True)
        notice.setProperty("role", "secondary")
        notice.setAccessibleName("保存状态")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        for child in (QLabel("标题（最多 60 字）"), title_input, QLabel("完整内容（最多 240 字）"), summary_input, notice, buttons):
            box.addWidget(child)

        def sync() -> None:
            if session.closed_reason:
                title_input.clear()
                summary_input.clear()
                dialog.reject()
                QMessageBox.information(widget, "回忆已更新", session.closed_reason)
            else:
                notice.setText(session.notice)

        def save() -> None:
            session.title, session.summary = title_input.text(), summary_input.toPlainText()
            action = album.change if radios["change"].isChecked() else album.correct
            try:
                check_character(album)
                action(session.memory_id, title=session.title, summary=session.summary,
                       expected_epoch=session.expected_epoch)
            except MemoryAlbumStaleError:
                refresh()
                if not session.closed_reason:
                    notice.setText(session.notice or "记忆刚刚有更新，检查后再保存。")
                return
            except (KeyError, ValueError, OSError, sqlite3.Error) as exc:
                session.on_save_failed(save_failure_reason(exc))
                notice.setText(session.notice)
                return
            dialog.accept()

        buttons.accepted.connect(save)
        buttons.rejected.connect(dialog.reject)
        open_edit.update(session=session, sync=sync, dialog=dialog)
        widget.memory_edit_dialog = dialog  # type: ignore[attr-defined]
        dialog.title_input, dialog.summary_input, dialog.notice, dialog.intents = title_input, summary_input, notice, radios
        dialog.save = save

        def finished(result: int) -> None:
            open_edit.clear()
            widget.memory_edit_dialog = None  # type: ignore[attr-defined]
            if result == QDialog.DialogCode.Accepted:
                refresh()
                notify()

        dialog.finished.connect(finished)
        dialog.open()

    def forget_selected() -> None:
        card = selected_card()
        if card is None:
            return
        try:
            album, epoch = edit_context()
            answer = QMessageBox.question(widget, "忘记这段回忆",
                                          "以后不再使用这条记忆，历史查询也不会恢复。\n正文还在本机存档，之后可以彻底删除。")
            if answer != QMessageBox.StandardButton.Yes:
                return
            check_character(album)
            album.forget(str(card["card_id"]), expected_epoch=epoch)
        except (KeyError, ValueError) as exc:
            show_error(exc)
            return
        refresh()
        notify()

    def purge_selected() -> None:
        card = selected_card()
        if card is None:
            return
        try:
            album, epoch = edit_context()
            answer = QMessageBox.question(widget, "彻底删除", PURGE_WARNING)
            if answer != QMessageBox.StandardButton.Yes:
                return
            check_character(album)
            album.purge(str(card["card_id"]), expected_epoch=epoch)
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
            album.remember_explicit(text, expected_epoch=epoch)
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
                album.confirm_pending(pending_id, expected_epoch=epoch)
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
            source_view.setPlainText("\n".join(part for part in (source_details_text(details), ledger_card_details(card)) if part))
            reveal_source()
        except (KeyError, ValueError) as exc:
            show_error(exc)

    def reveal_source() -> None:
        parent = widget.parentWidget()
        while parent is not None:
            if hasattr(parent, "ensureWidgetVisible"):
                parent.ensureWidgetVisible(source_view)
                return
            parent = parent.parentWidget()

    def show_claims(result: dict[str, object]) -> None:
        nonlocal claims_epoch
        claim_list.clear()
        view = result.get("presentation")
        evidence_label.setText(f"{view['label']}。{view['detail']}" if view else "这句话不需要查回忆。")
        evidence_label.show()
        claims_epoch = result.get("context_epoch")
        for claim in result.get("claims", []):
            item = QListWidgetItem(f"{claim['text']}\n点击查看依据")
            item.setData(Qt.ItemDataRole.UserRole + 1, dict(claim))
            claim_list.addItem(item)
        claim_list.setVisible(claim_list.count() > 0)

    def ask() -> None:
        query = ask_input.text().strip()
        album = current_album()
        if not query or album is None:
            return
        show_claims(album.ask(query))

    def show_turn_evidence() -> None:
        album = current_album()
        if album is not None:
            show_claims(album.turn_evidence())

    def expand_claim(item) -> None:
        claim = item.data(Qt.ItemDataRole.UserRole + 1)
        album = current_album()
        if not isinstance(claim, dict) or album is None:
            return
        result = album.expand({str(claim["memory_id"]): str(claim["fingerprint"])}, expected_epoch=int(claims_epoch))
        view = result["presentation"]
        if result["status"] != "sufficient":
            refresh()
            evidence_label.setText(f"{view['label']}。{view['detail']}")
            evidence_label.show()
            return
        lines = [result["note"]]
        lines += [source_details_text(card) for card in result["cards"]]
        lines += [f"你的原话：{span['text']}" for span in result["spans"]]
        source_view.setPlainText("\n".join(lines))
        reveal_source()

    def refresh_and_notify() -> None:
        refresh()
        if callable(on_changed):
            on_changed()
    refresh_button.clicked.connect(refresh_and_notify)
    list_widget.currentItemChanged.connect(update_actions)
    pin_button.clicked.connect(pin_selected)
    correct_button.clicked.connect(edit_selected)
    forget_button.clicked.connect(forget_selected)
    purge_button.clicked.connect(purge_selected)
    source_button.clicked.connect(show_source)
    remember_button.clicked.connect(remember_explicit)
    confirm_button.clicked.connect(lambda: resolve_pending(True))
    reject_button.clicked.connect(lambda: resolve_pending(False))
    ask_button.clicked.connect(ask)
    ask_input.returnPressed.connect(ask)
    claim_list.itemClicked.connect(expand_claim)
    refresh()
    widget.memory_list = list_widget  # type: ignore[attr-defined]
    widget.memory_source_view = source_view  # type: ignore[attr-defined]
    widget.memory_action_buttons = action_buttons  # type: ignore[attr-defined]
    widget.memory_pending_buttons = pending_buttons  # type: ignore[attr-defined]
    widget.memory_remember_button = remember_button  # type: ignore[attr-defined]
    widget.memory_ask_input = ask_input  # type: ignore[attr-defined]
    widget.memory_ask_button = ask_button  # type: ignore[attr-defined]
    widget.memory_claim_list = claim_list  # type: ignore[attr-defined]
    widget.memory_evidence_label = evidence_label  # type: ignore[attr-defined]
    widget.memory_edit_dialog = None  # type: ignore[attr-defined]
    widget.show_turn_evidence = show_turn_evidence  # type: ignore[attr-defined]
    widget.refresh_memory_album = refresh  # type: ignore[attr-defined]
    return widget
