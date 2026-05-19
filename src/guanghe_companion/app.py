from __future__ import annotations

import json
import sys

from collections.abc import Callable

from PySide6.QtCore import QPoint, QSize, QTimer, Qt, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .controller import CompanionController
from .expression_context import ExpressionContextChain, ManualPerceptionExpressionContextProvider
from .motion import MotionAnimator, load_default_motion_catalog
from .storage import DEMO_SAVE_PATH

MANUAL_PERCEPTION_NO_SCREEN_SUMMARY = "manual screen perception requested; no screen content was read"


class SpriteInteractionLabel(QLabel):
    def __init__(self, on_click: Callable[[], None], on_drag: Callable[[], None]) -> None:
        super().__init__()
        self.on_click = on_click
        self.on_drag = on_drag
        self._press_pos: QPoint | None = None
        self._dragged = False

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._press_pos = event.position().toPoint()
        self._dragged = False
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._press_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() >= 12:
            self._dragged = True
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press_pos is None:
            super().mouseReleaseEvent(event)
            return
        if self._dragged or (event.position().toPoint() - self._press_pos).manhattanLength() >= 12:
            self.on_drag()
        else:
            self.on_click()
        self._press_pos = None
        self._dragged = False
        event.accept()


class CompanionWindow(QMainWindow):
    def __init__(self, controller: CompanionController | None = None, desktop_mode: bool = False) -> None:
        super().__init__()
        self.controller = controller or CompanionController()
        self.desktop_mode = desktop_mode
        self.motion_catalog = load_default_motion_catalog()
        self.motion_animator = MotionAnimator(self.motion_catalog)
        self.spritesheet = QPixmap(str(self.motion_catalog.sheet_path))
        self.remaining_seconds = 15
        self.action_buttons: dict[str, QPushButton] = {}
        self.status_bars: dict[str, QProgressBar] = {}
        self._manual_perception_summary = ""
        self._base_expression_context_provider = self.controller.expression_context_provider
        self.controller.expression_context_provider = ExpressionContextChain(
            [self._base_expression_context_provider, self._manual_perception_context]
        )

        self.setWindowTitle("光核 AI 桌面伴侣 Demo")
        self.resize(1180, 760)
        self._build_ui()
        if self.desktop_mode:
            self._apply_desktop_mode()
        self._setup_timers()
        self._apply_snapshot(self.controller.get_snapshot())

    def closeEvent(self, event) -> None:
        self.controller.close()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(16, 16, 16, 16)
        shell.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(12)
        shell.addLayout(top, stretch=1)

        self.hero_card = self._build_hero_card()
        top.addWidget(self.hero_card, stretch=3)

        self.status_card = self._build_status_card()
        top.addWidget(self.status_card, stretch=2)

        self.feedback_card = self._build_feedback_card()
        shell.addWidget(self.feedback_card)

        self.actions_card = self._build_actions_card()
        shell.addWidget(self.actions_card)

        self.demo_card = self._build_demo_card()
        shell.addWidget(self.demo_card)

        self.perception_card = self._build_perception_card()
        shell.addWidget(self.perception_card)

        lower = QHBoxLayout()
        lower.setSpacing(12)
        shell.addLayout(lower, stretch=1)
        self.shop_card = self._build_shop_card()
        self.inventory_card = self._build_inventory_card()
        lower.addWidget(self.shop_card, stretch=1)
        lower.addWidget(self.inventory_card, stretch=1)

    def _build_hero_card(self) -> QGroupBox:
        box = QGroupBox("角色动画区")
        layout = QVBoxLayout(box)
        self.sprite_label = SpriteInteractionLabel(
            on_click=lambda: self._handle_action("touch"),
            on_drag=lambda: self._handle_action("drag"),
        )
        self.sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite_label.setStyleSheet(
            "QLabel { border: 2px dashed #4f6d7a; border-radius: 18px; padding: 12px; background: #f7fbfd; }"
        )
        self.sprite_label.setMinimumHeight(300)
        layout.addWidget(self.sprite_label)
        self.item_feedback_label = QLabel()
        self.item_feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.item_feedback_label.setFixedSize(72, 72)
        self.item_feedback_label.setStyleSheet(
            "QLabel { border: 1px solid #d7e3ea; border-radius: 10px; background: rgba(255, 255, 255, 220); }"
        )
        self.item_feedback_label.hide()
        layout.addWidget(self.item_feedback_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.character_label = QLabel()
        self.character_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.character_label.setStyleSheet(
            "QLabel { border: 1px solid #d7e3ea; border-radius: 14px; padding: 18px; background: #ffffff; font-size: 16px; }"
        )
        self.character_label.setMinimumHeight(160)
        layout.addWidget(self.character_label)
        return box

    def _build_status_card(self) -> QGroupBox:
        box = QGroupBox("状态面板")
        layout = QVBoxLayout(box)

        self.mode_label = QLabel()
        self.resources_label = QLabel()
        self.goal_label = QLabel()
        self.relationship_label = QLabel()
        self.tick_label = QLabel()
        for widget in (self.mode_label, self.resources_label, self.goal_label, self.relationship_label, self.tick_label):
            widget.setWordWrap(True)
            layout.addWidget(widget)

        grid = QGridLayout()
        layout.addLayout(grid)
        for row, stat_name in enumerate(("focus", "charge", "stability", "mood", "trust")):
            label = QLabel(stat_name)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFormat("%v / 100")
            self.status_bars[stat_name] = bar
            grid.addWidget(label, row, 0)
            grid.addWidget(bar, row, 1)
        return box

    def _build_feedback_card(self) -> QGroupBox:
        box = QGroupBox("反馈气泡")
        layout = QVBoxLayout(box)
        self.feedback_label = QLabel()
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet("font-size: 16px;")
        self.delta_label = QLabel()
        self.delta_label.setWordWrap(True)
        self.events_label = QLabel()
        self.events_label.setWordWrap(True)
        self.events_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.events_label.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; background: #f7fbfd; padding: 8px; border-radius: 8px;")
        self.memory_label = QLabel()
        self.memory_label.setWordWrap(True)
        self.memory_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.memory_label.setStyleSheet("font-size: 13px; background: #fffaf0; padding: 8px; border-radius: 8px;")
        layout.addWidget(self.feedback_label)
        layout.addWidget(self.delta_label)
        layout.addWidget(self.events_label)
        layout.addWidget(self.memory_label)
        return box

    def _build_actions_card(self) -> QGroupBox:
        box = QGroupBox("主按钮动作")
        layout = QHBoxLayout(box)
        for action_id in ("touch", "soothe", "rest", "study", "play", "drag"):
            button = QPushButton(action_id)
            button.clicked.connect(lambda checked=False, current=action_id: self._handle_action(current))
            button.setMinimumHeight(42)
            self.action_buttons[action_id] = button
            layout.addWidget(button)
        return box

    def _build_demo_card(self) -> QGroupBox:
        box = QGroupBox("演示触发")
        layout = QHBoxLayout(box)
        self.demo_reset_button = QPushButton("重置演示状态")
        self.demo_reset_button.clicked.connect(self._handle_demo_reset)
        self.demo_low_charge_button = QPushButton("模拟低能量")
        self.demo_low_charge_button.clicked.connect(lambda: self._handle_demo_proactive("low_charge"))
        self.demo_quiet_mood_button = QPushButton("模拟久未互动")
        self.demo_quiet_mood_button.clicked.connect(lambda: self._handle_demo_proactive("quiet_mood"))
        for button in (self.demo_reset_button, self.demo_low_charge_button, self.demo_quiet_mood_button):
            button.setMinimumHeight(36)
            layout.addWidget(button)
        return box

    def _build_perception_card(self) -> QGroupBox:
        box = QGroupBox("屏幕感知")
        layout = QVBoxLayout(box)
        self.perception_status_label = QLabel("屏幕感知：关闭")
        self.perception_status_label.setWordWrap(True)
        self.perception_privacy_label = QLabel("默认不会读取屏幕；只在手动触发时显示隐私提示。本轮不会自动截图。")
        self.perception_privacy_label.setWordWrap(True)
        self.observe_screen_button = QPushButton("手动触发屏幕感知")
        self.observe_screen_button.setMinimumHeight(36)
        self.observe_screen_button.clicked.connect(self._handle_manual_screen_perception)
        layout.addWidget(self.perception_status_label)
        layout.addWidget(self.perception_privacy_label)
        layout.addWidget(self.observe_screen_button)
        return box

    def _build_shop_card(self) -> QGroupBox:
        box = QGroupBox("轻量商店")
        layout = QVBoxLayout(box)
        self.shop_list = QListWidget()
        self.shop_list.setIconSize(QSize(36, 36))
        layout.addWidget(self.shop_list)
        self.buy_button = QPushButton("购买选中物品")
        self.buy_button.clicked.connect(self._handle_buy)
        layout.addWidget(self.buy_button)
        return box

    def _build_inventory_card(self) -> QGroupBox:
        box = QGroupBox("轻量背包")
        layout = QVBoxLayout(box)
        self.inventory_list = QListWidget()
        self.inventory_list.setIconSize(QSize(36, 36))
        layout.addWidget(self.inventory_list)
        actions = QHBoxLayout()
        self.feed_button = QPushButton("使用/投喂")
        self.feed_button.clicked.connect(lambda: self._handle_inventory_usage("feed"))
        self.gift_button = QPushButton("赠送")
        self.gift_button.clicked.connect(lambda: self._handle_inventory_usage("gift"))
        self.tick_button = QPushButton("立即结算 15 秒")
        self.tick_button.clicked.connect(self._handle_tick)
        actions.addWidget(self.feed_button)
        actions.addWidget(self.gift_button)
        actions.addWidget(self.tick_button)
        layout.addLayout(actions)
        return box

    def _apply_desktop_mode(self) -> None:
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.status_card.hide()
        self.feedback_card.hide()
        self.actions_card.hide()
        self.demo_card.hide()
        self.perception_card.hide()
        self.shop_card.hide()
        self.inventory_card.hide()
        self.resize(360, 420)

    def _setup_timers(self) -> None:
        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self._advance_frame)
        self.frame_timer.start(self.motion_animator.interval_ms())

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._handle_tick)
        self.tick_timer.start(15_000)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_timer.start(1_000)

    @Slot()
    def _update_countdown(self) -> None:
        self.remaining_seconds = 15 if self.remaining_seconds <= 1 else self.remaining_seconds - 1
        snapshot = self.controller.get_snapshot()
        self.tick_label.setText(f"15 秒 tick：已结算 {snapshot['tick_count']} 次，下一轮 {self.remaining_seconds} 秒后")

    def _reset_countdown(self) -> None:
        self.remaining_seconds = 15

    @Slot()
    def _handle_tick(self) -> None:
        self._reset_countdown()
        self._apply_snapshot(self.controller.advance_tick(include_ai_expression=False))

    @Slot()
    def _advance_frame(self) -> None:
        self.motion_animator.advance()
        self._render_current_frame()

    def _handle_action(self, action_id: str) -> None:
        self._apply_snapshot(self.controller.perform_action(action_id, include_ai_expression=False))

    def _handle_demo_proactive(self, scenario: str) -> None:
        self._reset_countdown()
        self._apply_snapshot(self.controller.trigger_demo_proactive(scenario, include_ai_expression=False))

    def _handle_demo_reset(self) -> None:
        self._reset_countdown()
        self._apply_snapshot(self.controller.reset_demo_state(include_ai_expression=False))

    def _handle_manual_screen_perception(self) -> None:
        QMessageBox.information(
            self,
            "屏幕感知隐私提示",
            "屏幕感知只在手动触发时运行。本轮不会自动截图、不会上传屏幕、不会长期记录原始截图。",
        )
        self.perception_status_label.setText("屏幕感知：已手动触发（未读取屏幕内容）")

        self._manual_perception_summary = MANUAL_PERCEPTION_NO_SCREEN_SUMMARY

    def _manual_perception_context(self) -> dict[str, object]:
        return ManualPerceptionExpressionContextProvider(
            summary=self._manual_perception_summary,
            enabled=bool(self._manual_perception_summary),
        )()

    @Slot()
    def _handle_buy(self) -> None:
        item_id = self._current_item_id(self.shop_list)
        if not item_id:
            self._show_message("请先在商店中选择一个物品。")
            return
        try:
            self._apply_snapshot(self.controller.buy_selected_item(item_id, include_ai_expression=False))
        except ValueError as exc:
            self._show_message(str(exc))

    def _handle_inventory_usage(self, usage: str) -> None:
        item_id = self._current_item_id(self.inventory_list)
        if not item_id:
            self._show_message("请先在背包中选择一个物品。")
            return
        try:
            self._apply_snapshot(self.controller.use_selected_item(item_id, usage=usage, include_ai_expression=False))
        except ValueError as exc:
            self._show_message(str(exc))

    def _apply_snapshot(self, snapshot: dict[str, object]) -> None:
        self.motion_animator.set_motion(str(snapshot["motion"]))
        self.frame_timer.setInterval(self.motion_animator.interval_ms())
        self._render_current_frame()
        self.character_label.setText(
            f"{snapshot['character_name']}\n{snapshot['character_title']}\n\n"
            f"模式：{snapshot['mode']}\n"
            f"动作：{snapshot['motion_caption']}\n\n"
            f"{snapshot['character_description']}"
        )
        self.mode_label.setText(f"当前模式：{snapshot['mode']}")
        self.resources_label.setText(
            f"coins {snapshot['coins']} / level {snapshot['level']} / exp {snapshot['exp']}"
        )
        self.goal_label.setText(str(snapshot["goal"]))
        self.relationship_label.setText(
            f"当前关系：{snapshot['relationship_stage']}\n下个解锁：{snapshot['next_relationship_unlock']}"
        )
        self.tick_label.setText(f"15 秒 tick：已结算 {snapshot['tick_count']} 次，下一轮 {self.remaining_seconds} 秒后")

        for stat_name, bar in self.status_bars.items():
            bar.setValue(int(float(snapshot[stat_name])))

        self.feedback_label.setText(str(snapshot["feedback"]))
        self.delta_label.setText(f"最近变化：{snapshot['delta_text']}")
        self.events_label.setText("\n".join(str(line) for line in snapshot["event_preview"].splitlines()))
        self.memory_label.setText(self._format_memory_log(snapshot["memory_log"]))

        actions = {entry["action_id"]: entry for entry in snapshot["actions"]}
        for action_id, button in self.action_buttons.items():
            entry = actions[action_id]
            button.setText(str(entry["label"]))
            button.setEnabled(bool(entry["enabled"]))

        self._fill_list(self.shop_list, snapshot["shop_items"], kind="shop")
        self._fill_list(self.inventory_list, snapshot["inventory_items"], kind="inventory")
        self._sync_inventory_buttons(snapshot["inventory_items"])
        self._show_item_feedback(str(snapshot.get("item_feedback_icon") or ""))

    def _render_current_frame(self) -> None:
        if self.spritesheet.isNull():
            self.sprite_label.setText("spritesheet 未找到")
            return
        rect = self.motion_animator.current_frame_rect()
        frame = self.spritesheet.copy(rect)
        scaled = frame.scaled(
            288,
            312,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.sprite_label.setPixmap(scaled)

    def _fill_list(self, widget: QListWidget, items: object, kind: str) -> None:
        current = self._current_item_id(widget)
        widget.clear()
        for item in items:
            row = QListWidgetItem()
            if kind == "shop":
                text = f"{item['name']} | {item['category']} | {item['price']} coins"
                if not item["unlocked"]:
                    text += " | 未解锁"
                elif not item["affordable"]:
                    text += " | 金币不足"
            else:
                text = f"{item['name']} | {item['category']} | x{item['count']}"
            row.setText(text)
            icon_path = str(item.get("icon_path") or "")
            if icon_path:
                row.setIcon(QIcon(icon_path))
            row.setData(Qt.ItemDataRole.UserRole, item["item_id"])
            widget.addItem(row)
            if current and item["item_id"] == current:
                widget.setCurrentItem(row)

    def _show_item_feedback(self, icon_path: str) -> None:
        if not icon_path:
            self.item_feedback_label.hide()
            return
        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            self.item_feedback_label.hide()
            return
        self.item_feedback_label.setPixmap(
            pixmap.scaled(
                56,
                56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.item_feedback_label.show()
        QTimer.singleShot(1_400, self.item_feedback_label.hide)

    def _format_memory_log(self, entries: object) -> str:
        if not entries:
            return "回忆日志：暂无回忆"
        lines = ["回忆日志："]
        for entry in list(entries)[:5]:
            lines.append(f"- {entry['kind']}：{entry['summary']}")
        return "\n".join(lines)

    def _sync_inventory_buttons(self, items: object) -> None:
        selected_id = self._current_item_id(self.inventory_list)
        current = None
        for item in items:
            if item["item_id"] == selected_id:
                current = item
                break
        if current is None:
            self.feed_button.setEnabled(False)
            self.gift_button.setEnabled(False)
            return
        self.feed_button.setEnabled(bool(current["can_feed"] or current["can_use"]))
        self.gift_button.setEnabled(bool(current["can_gift"]))

    def _current_item_id(self, widget: QListWidget) -> str | None:
        current = widget.currentItem()
        if current is None:
            return None
        return str(current.data(Qt.ItemDataRole.UserRole))

    def _show_message(self, message: str) -> None:
        QMessageBox.information(self, "提示", message)


def should_use_desktop_mode(argv: list[str]) -> bool:
    return "--desktop-mode" in argv or "--pet-mode" in argv


def should_use_demo_save(argv: list[str]) -> bool:
    return "--demo-save" in argv or "--reset-demo-save" in argv


def should_reset_demo_save(argv: list[str]) -> bool:
    return "--reset-demo-save" in argv


def launch(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    app = QApplication.instance() or QApplication(args)
    controller = CompanionController(save_path=DEMO_SAVE_PATH) if should_use_demo_save(args) else CompanionController()
    if should_reset_demo_save(args):
        controller.reset_demo_state()
    window = CompanionWindow(controller=controller, desktop_mode=should_use_desktop_mode(args))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(launch())
