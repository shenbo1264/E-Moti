from __future__ import annotations

import json
import sys

from collections.abc import Callable

from PySide6.QtCore import QPoint, QRect, QSize, QTimer, Qt, Slot
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QStackedWidget,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from .controller import CompanionController
from .dialogue import DialogueRequest
from .expression_context import ExpressionContextChain, ManualPerceptionExpressionContextProvider
from .motion import MotionAnimator, load_default_motion_catalog
from .storage import DEMO_SAVE_PATH

MANUAL_PERCEPTION_NO_SCREEN_SUMMARY = "manual screen perception requested; no screen content was read"
DESKTOP_DOCK_THRESHOLD_PX = 32
CONTROL_PANEL_SPRITE_MIN_HEIGHT = 300
DESKTOP_SPRITE_WIDTH = 288
DESKTOP_SPRITE_HEIGHT = 312
DESKTOP_WINDOW_WIDTH = 320
DESKTOP_WINDOW_HEIGHT = 424
MAX_QT_WIDGET_SIZE = 16_777_215
CONTROL_PANEL_SPRITE_STYLE = (
    "QLabel { border: 1px solid #cbdde5; border-radius: 8px; "
    "padding: 12px; background: #f7fbfd; }"
)
DESKTOP_SPRITE_STYLE = "QLabel { border: none; padding: 0; background: transparent; }"
DESKTOP_HERO_STYLE = "QGroupBox { border: none; margin: 0; padding: 0; background: transparent; }"
APP_FONT_FAMILY = "Microsoft YaHei UI"
STAT_LABELS = {
    "focus": "专注",
    "charge": "能量",
    "stability": "稳定",
    "mood": "心情",
    "trust": "信任",
}
APP_STYLE_SHEET = """
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial";
    color: #263238;
    font-size: 13px;
}
#CompanionRoot {
    background: #f4f7f8;
}
QFrame#LauncherCard {
    background: #ffffff;
    border-bottom: 1px solid #d6e1e7;
}
QFrame#SidebarCard {
    background: #ffffff;
    border: 1px solid #d6e1e7;
    border-radius: 8px;
}
QLabel#NavigationHint {
    color: #445b66;
    font-size: 13px;
    font-weight: 800;
}
QPushButton#NavigationButton {
    text-align: left;
    padding: 9px 12px;
}
QPushButton#NavigationButton:checked {
    background: #e6f2f5;
    border-color: #7ba5b5;
    color: #1f5360;
}
QLabel#LauncherEyebrow {
    color: #5d7380;
    font-size: 12px;
    font-weight: 700;
}
QLabel#LauncherTitle {
    color: #1f343d;
    font-size: 26px;
    font-weight: 800;
}
QLabel#LauncherSubtitle {
    color: #536a75;
    font-size: 13px;
}
QPushButton#PrimaryLaunchButton {
    background: #1f7a8c;
    border-color: #1f7a8c;
    color: #ffffff;
    font-size: 15px;
    padding: 10px 22px;
}
QPushButton#PrimaryLaunchButton:hover {
    background: #256f7c;
    border-color: #256f7c;
}
QGroupBox {
    background: #ffffff;
    border: 1px solid #d6e1e7;
    border-radius: 8px;
    margin-top: 16px;
    padding: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #39525f;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #b8c9d2;
    border-radius: 8px;
    padding: 8px 14px;
    color: #263238;
    font-weight: 600;
}
QPushButton:hover {
    background: #edf5f8;
    border-color: #6d94a6;
}
QPushButton:pressed {
    background: #dfecef;
}
QPushButton:disabled {
    color: #94a3ab;
    background: #f4f6f7;
    border-color: #d7e0e5;
}
QProgressBar {
    border: 1px solid #c9d7dd;
    border-radius: 7px;
    background: #f7fafb;
    text-align: center;
    min-height: 16px;
}
QProgressBar::chunk {
    border-radius: 6px;
    background: #5b9db4;
}
QListWidget {
    background: #ffffff;
    border: 1px solid #d6e1e7;
    border-radius: 8px;
    padding: 6px;
}
QListWidget::item {
    min-height: 38px;
    padding: 4px 8px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background: #e6f2f5;
    color: #20333c;
}
"""


def configure_application_style(app: QApplication | None = None) -> bool:
    target = app if app is not None else QApplication.instance()
    if target is None:
        return False
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None and hasattr(target, "setStyle"):
        target.setStyle(fusion)
    if hasattr(target, "setFont"):
        target.setFont(QFont(APP_FONT_FAMILY, 10))
    if hasattr(target, "setStyleSheet"):
        target.setStyleSheet(APP_STYLE_SHEET)
    return True


class SpriteInteractionLabel(QLabel):
    def __init__(
        self,
        on_click: Callable[[], None],
        on_drag: Callable[[], None],
        on_drag_move: Callable[[QPoint], None] | None = None,
    ) -> None:
        super().__init__()
        self.on_click = on_click
        self.on_drag = on_drag
        self.on_drag_move = on_drag_move
        self._press_global_pos: QPoint | None = None
        self._last_drag_global_pos: QPoint | None = None
        self._dragged = False

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._press_global_pos = event.globalPosition().toPoint()
        self._last_drag_global_pos = self._press_global_pos
        self._dragged = False
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._press_global_pos is None:
            super().mouseMoveEvent(event)
            return
        current_pos = event.globalPosition().toPoint()
        if (current_pos - self._press_global_pos).manhattanLength() >= 12:
            self._dragged = True
            if self.on_drag_move is not None and self._last_drag_global_pos is not None:
                self.on_drag_move(current_pos - self._last_drag_global_pos)
                self._last_drag_global_pos = current_pos
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press_global_pos is None:
            super().mouseReleaseEvent(event)
            return
        if self._dragged or (event.globalPosition().toPoint() - self._press_global_pos).manhattanLength() >= 12:
            self.on_drag()
        else:
            self.on_click()
        self._press_global_pos = None
        self._last_drag_global_pos = None
        self._dragged = False
        event.accept()


class CompanionWindow(QMainWindow):
    def __init__(
        self,
        controller: CompanionController | None = None,
        desktop_mode: bool = False,
        *,
        advance_ticks: bool = True,
        owns_controller: bool = True,
    ) -> None:
        super().__init__()
        self.controller = controller or CompanionController()
        self.desktop_mode = desktop_mode
        self._advance_ticks = advance_ticks
        self._owns_controller = owns_controller
        self.desktop_pet_window: CompanionWindow | None = None
        self._return_target_window: CompanionWindow | None = None
        self._close_callbacks: list[Callable[[CompanionWindow], None]] = []
        self.motion_catalog = load_default_motion_catalog()
        self.motion_animator = MotionAnimator(self.motion_catalog)
        self.spritesheet = QPixmap(str(self.motion_catalog.sheet_path))
        self.remaining_seconds = 15
        self.action_buttons: dict[str, QPushButton] = {}
        self.navigation_buttons: list[QPushButton] = []
        self.status_bars: dict[str, QProgressBar] = {}
        self.stat_name_labels: list[QLabel] = []
        self._manual_perception_summary = ""
        self._base_expression_context_provider = self.controller.expression_context_provider
        self.controller.expression_context_provider = ExpressionContextChain(
            [self._base_expression_context_provider, self._manual_perception_context]
        )

        configure_application_style(QApplication.instance())
        self.setWindowTitle("星汐 E-Moti 桌面伴侣")
        self.resize(1180, 760)
        self._build_ui()
        if self.desktop_mode:
            self._apply_desktop_mode()
        self._setup_timers()
        self._apply_snapshot(self.controller.get_snapshot())

    def _register_close_callback(self, callback: Callable[["CompanionWindow"], None]) -> None:
        self._close_callbacks.append(callback)

    def closeEvent(self, event) -> None:
        pet_window = self.desktop_pet_window
        if pet_window is not None:
            self.desktop_pet_window = None
            pet_window.close()
        self._manual_perception_summary = ""
        self.controller.expression_context_provider = self._base_expression_context_provider
        try:
            if self._owns_controller:
                self.controller.close()
        except Exception:
            pass
        finally:
            super().closeEvent(event)
            for callback in tuple(self._close_callbacks):
                callback(self)

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("CompanionRoot")
        self.root_widget = root
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        self.shell_layout = shell
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.launcher_card = self._build_launcher_card()
        shell.addWidget(self.launcher_card)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        self.control_panel_content_layout = content_layout
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        shell.addWidget(content, stretch=1)

        self.sidebar_card = self._build_sidebar_card()
        content_layout.addWidget(self.sidebar_card)

        self.content_stack = QStackedWidget()
        self.control_panel_page_layouts: list[QVBoxLayout] = []
        content_layout.addWidget(self.content_stack, stretch=1)

        overview_page = QWidget()
        overview_layout = QVBoxLayout(overview_page)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(12)
        self.control_panel_page_layouts.append(overview_layout)

        top = QHBoxLayout()
        top.setSpacing(12)
        overview_layout.addLayout(top, stretch=1)

        self.hero_card = self._build_hero_card()
        top.addWidget(self.hero_card, stretch=3)

        self.status_card = self._build_status_card()
        top.addWidget(self.status_card, stretch=2)

        self.feedback_card = self._build_feedback_card()
        overview_layout.addWidget(self.feedback_card)
        self.content_stack.addWidget(overview_page)

        interaction_page = QWidget()
        interaction_layout = QVBoxLayout(interaction_page)
        interaction_layout.setContentsMargins(0, 0, 0, 0)
        interaction_layout.setSpacing(12)
        self.control_panel_page_layouts.append(interaction_layout)

        self.actions_card = self._build_actions_card()
        interaction_layout.addWidget(self.actions_card)

        self.demo_card = self._build_demo_card()
        interaction_layout.addWidget(self.demo_card)
        interaction_layout.addStretch(1)
        self.content_stack.addWidget(interaction_page)

        inventory_page = QWidget()
        inventory_layout = QVBoxLayout(inventory_page)
        inventory_layout.setContentsMargins(0, 0, 0, 0)
        inventory_layout.setSpacing(12)
        self.control_panel_page_layouts.append(inventory_layout)

        lower = QHBoxLayout()
        lower.setSpacing(12)
        inventory_layout.addLayout(lower, stretch=1)
        self.shop_card = self._build_shop_card()
        self.inventory_card = self._build_inventory_card()
        lower.addWidget(self.shop_card, stretch=1)
        lower.addWidget(self.inventory_card, stretch=1)
        self.content_stack.addWidget(inventory_page)

        privacy_page = QWidget()
        privacy_layout = QVBoxLayout(privacy_page)
        privacy_layout.setContentsMargins(0, 0, 0, 0)
        privacy_layout.setSpacing(12)
        self.control_panel_page_layouts.append(privacy_layout)
        self.perception_card = self._build_perception_card()
        privacy_layout.addWidget(self.perception_card)
        privacy_layout.addStretch(1)
        self.content_stack.addWidget(privacy_page)

    def _build_sidebar_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SidebarCard")
        frame.setFixedWidth(154)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(8)

        self.navigation_hint_label = QLabel("控制中心")
        self.navigation_hint_label.setObjectName("NavigationHint")
        layout.addWidget(self.navigation_hint_label)

        for index, label in enumerate(("总览", "互动", "背包", "隐私")):
            button = QPushButton(label)
            button.setObjectName("NavigationButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, current=index: self._select_navigation_button(current))
            self.navigation_buttons.append(button)
            layout.addWidget(button)
        self.navigation_buttons[0].setChecked(True)

        layout.addStretch(1)
        return frame

    def _select_navigation_button(self, selected_index: int) -> None:
        for index, button in enumerate(self.navigation_buttons):
            button.setChecked(index == selected_index)
        if hasattr(self, "content_stack"):
            self.content_stack.setCurrentIndex(selected_index)

    def _build_launcher_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("LauncherCard")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(16)

        copy = QVBoxLayout()
        copy.setSpacing(4)
        self.launcher_eyebrow_label = QLabel("原创 OC 桌面伴侣 Demo")
        self.launcher_eyebrow_label.setObjectName("LauncherEyebrow")
        self.launcher_title_label = QLabel("星汐 E-Moti")
        self.launcher_title_label.setObjectName("LauncherTitle")
        self.launcher_subtitle_label = QLabel("控制面板用于演示状态、背包和关系；桌宠模式是独立桌面演出窗口。")
        self.launcher_subtitle_label.setObjectName("LauncherSubtitle")
        self.launcher_subtitle_label.setWordWrap(True)
        copy.addWidget(self.launcher_eyebrow_label)
        copy.addWidget(self.launcher_title_label)
        copy.addWidget(self.launcher_subtitle_label)

        self.enter_desktop_mode_button = QPushButton("进入桌宠模式")
        self.enter_desktop_mode_button.setObjectName("PrimaryLaunchButton")
        self.enter_desktop_mode_button.setMinimumHeight(44)
        self.enter_desktop_mode_button.clicked.connect(self._enter_desktop_mode)

        layout.addLayout(copy, stretch=1)
        layout.addWidget(self.enter_desktop_mode_button)
        return frame

    def _build_hero_card(self) -> QGroupBox:
        box = QGroupBox("角色动画区")
        layout = QVBoxLayout(box)
        self.hero_layout = layout
        self.sprite_label = SpriteInteractionLabel(
            on_click=lambda: self._handle_action("touch"),
            on_drag=lambda: self._handle_action("drag"),
            on_drag_move=self._move_desktop_window_by,
        )
        self.sprite_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sprite_label.customContextMenuRequested.connect(
            lambda pos: self._show_desktop_context_menu(self.sprite_label.mapToGlobal(pos))
        )
        self.sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite_label.setStyleSheet(CONTROL_PANEL_SPRITE_STYLE)
        self.sprite_label.setMinimumHeight(CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        layout.addWidget(self.sprite_label)
        self.desktop_feedback_label = QLabel()
        self.desktop_feedback_label.setWordWrap(True)
        self.desktop_feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desktop_feedback_label.setStyleSheet(
            "QLabel { border: 1px solid rgba(79, 109, 122, 140); border-radius: 10px; "
            "padding: 8px 10px; background: rgba(255, 255, 255, 225); font-size: 13px; }"
        )
        self.desktop_feedback_label.hide()
        layout.addWidget(self.desktop_feedback_label)
        self.dialogue_bar = QFrame()
        self.dialogue_bar.setObjectName("DesktopDialogueBar")
        self.dialogue_bar.setStyleSheet(
            "QFrame#DesktopDialogueBar { border: 1px solid rgba(80, 112, 126, 150); border-radius: 8px; "
            "background: rgba(255, 255, 255, 232); }"
        )
        dialogue_layout = QHBoxLayout(self.dialogue_bar)
        dialogue_layout.setContentsMargins(8, 6, 8, 6)
        dialogue_layout.setSpacing(6)
        self.dialogue_input = QLineEdit()
        self.dialogue_input.setPlaceholderText("和星汐说点什么")
        self.dialogue_input.setMinimumHeight(30)
        self.dialogue_input.setStyleSheet(
            "QLineEdit { border: 1px solid #b8c9d2; border-radius: 6px; padding: 4px 8px; "
            "background: #ffffff; }"
        )
        self.dialogue_input.returnPressed.connect(self._handle_dialogue_submit)
        self.dialogue_send_button = QPushButton("发送")
        self.dialogue_send_button.setMinimumHeight(30)
        self.dialogue_send_button.clicked.connect(self._handle_dialogue_submit)
        dialogue_layout.addWidget(self.dialogue_input, stretch=1)
        dialogue_layout.addWidget(self.dialogue_send_button)
        self.dialogue_bar.hide()
        layout.addWidget(self.dialogue_bar)
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
        box = QGroupBox("星汐状态")
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
            label = QLabel(STAT_LABELS[stat_name])
            self.stat_name_labels.append(label)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFormat("%v / 100")
            self.status_bars[stat_name] = bar
            grid.addWidget(label, row, 0)
            grid.addWidget(bar, row, 1)
        return box

    def _build_feedback_card(self) -> QGroupBox:
        box = QGroupBox("近期回应")
        layout = QVBoxLayout(box)
        self.feedback_label = QLabel()
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #1f343d;")
        self.delta_label = QLabel()
        self.delta_label.setWordWrap(True)
        self.events_label = QLabel()
        self.events_label.setWordWrap(True)
        self.events_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.events_label.setStyleSheet("font-size: 13px; background: #f7fbfd; padding: 8px; border-radius: 8px;")
        self.memory_label = QLabel()
        self.memory_label.setWordWrap(True)
        self.memory_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.memory_label.setStyleSheet("font-size: 13px; background: #fff8ef; padding: 8px; border-radius: 8px;")
        layout.addWidget(self.feedback_label)
        layout.addWidget(self.delta_label)
        layout.addWidget(self.events_label)
        layout.addWidget(self.memory_label)
        return box

    def _build_actions_card(self) -> QGroupBox:
        box = QGroupBox("互动动作")
        layout = QHBoxLayout(box)
        for action_id in ("touch", "soothe", "rest", "study", "play", "drag"):
            button = QPushButton(action_id)
            button.clicked.connect(lambda checked=False, current=action_id: self._handle_action(current))
            button.setMinimumHeight(42)
            self.action_buttons[action_id] = button
            layout.addWidget(button)
        return box

    def _build_demo_card(self) -> QGroupBox:
        box = QGroupBox("演示工具")
        layout = QHBoxLayout(box)
        self.demo_reset_button = QPushButton("重置演示状态")
        self.demo_reset_button.clicked.connect(self._handle_demo_reset)
        self.demo_low_charge_button = QPushButton("模拟低能量")
        self.demo_low_charge_button.clicked.connect(lambda: self._handle_demo_proactive("low_charge"))
        self.demo_quiet_mood_button = QPushButton("模拟久未互动")
        self.demo_quiet_mood_button.clicked.connect(lambda: self._handle_demo_proactive("quiet_mood"))
        for button in (
            self.demo_reset_button,
            self.demo_low_charge_button,
            self.demo_quiet_mood_button,
        ):
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
        self.desktop_mode = True
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        for widget in (self.root_widget, self.hero_card, self.sprite_label):
            widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            widget.setAutoFillBackground(False)
        self.root_widget.setStyleSheet("background: transparent;")
        self.shell_layout.setContentsMargins(0, 0, 0, 0)
        self.shell_layout.setSpacing(0)
        self.control_panel_content_layout.setContentsMargins(0, 0, 0, 0)
        self.control_panel_content_layout.setSpacing(0)
        for page_layout in self.control_panel_page_layouts:
            page_layout.setSpacing(0)
        self.launcher_card.hide()
        self.sidebar_card.hide()
        self.status_card.hide()
        self.feedback_card.hide()
        self.actions_card.hide()
        self.demo_card.hide()
        self.perception_card.hide()
        self.shop_card.hide()
        self.inventory_card.hide()
        self.hero_card.setTitle("")
        self.hero_card.setStyleSheet(DESKTOP_HERO_STYLE)
        self.hero_layout.setContentsMargins(0, 0, 0, 0)
        self.hero_layout.setSpacing(6)
        self.hero_layout.setAlignment(self.sprite_label, Qt.AlignmentFlag.AlignHCenter)
        self.hero_layout.setAlignment(self.desktop_feedback_label, Qt.AlignmentFlag.AlignHCenter)
        self.hero_layout.setAlignment(self.dialogue_bar, Qt.AlignmentFlag.AlignHCenter)
        self.character_label.hide()
        self.desktop_feedback_label.hide()
        self.dialogue_bar.show()
        self.item_feedback_label.hide()
        self.sprite_label.setStyleSheet(DESKTOP_SPRITE_STYLE)
        self.sprite_label.setFixedSize(DESKTOP_SPRITE_WIDTH, DESKTOP_SPRITE_HEIGHT)
        self.desktop_feedback_label.setFixedWidth(DESKTOP_WINDOW_WIDTH)
        self.dialogue_bar.setFixedWidth(DESKTOP_WINDOW_WIDTH)
        self.setFixedSize(DESKTOP_WINDOW_WIDTH, DESKTOP_WINDOW_HEIGHT)

    def _enter_desktop_mode(self) -> None:
        if self.desktop_mode:
            return
        if self.desktop_pet_window is not None:
            self.desktop_pet_window.show()
            self.desktop_pet_window.raise_()
            self.desktop_pet_window.activateWindow()
            return
        pet_window = CompanionWindow(
            controller=self.controller,
            desktop_mode=True,
            advance_ticks=False,
            owns_controller=False,
        )
        pet_window._return_target_window = self
        pet_window._register_close_callback(self._handle_desktop_pet_closed)
        self.desktop_pet_window = pet_window
        pet_window.show()
        pet_window._apply_snapshot(self.controller.get_snapshot())

    def _handle_desktop_pet_closed(self, window: "CompanionWindow") -> None:
        if self.desktop_pet_window is window:
            self.desktop_pet_window = None

    def _build_desktop_context_menu(self) -> QMenu:
        menu = QMenu(self)
        status_action = QAction("状态面板", self)
        status_action.triggered.connect(self._show_desktop_status_panel)
        history_action = QAction("对话历史", self)
        history_action.triggered.connect(self._show_dialogue_history_panel)
        clear_history_action = QAction("清屏", self)
        clear_history_action.triggered.connect(self._clear_dialogue_history)
        copy_history_action = QAction("复制对话", self)
        copy_history_action.triggered.connect(self._copy_dialogue_history_to_clipboard)
        replay_history_action = QAction("回放上一句", self)
        replay_history_action.triggered.connect(self._replay_latest_dialogue)
        revert_history_action = QAction("回溯上一轮", self)
        revert_history_action.triggered.connect(self._revert_dialogue_history)
        return_action = QAction("返回控制面板", self)
        return_action.triggered.connect(self._return_to_control_panel)
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        menu.addAction(status_action)
        menu.addAction(history_action)
        menu.addAction(clear_history_action)
        menu.addAction(copy_history_action)
        menu.addAction(replay_history_action)
        menu.addAction(revert_history_action)
        menu.addSeparator()
        menu.addAction(return_action)
        menu.addAction(exit_action)
        return menu

    def contextMenuEvent(self, event) -> None:
        if not self.desktop_mode:
            super().contextMenuEvent(event)
            return
        self._show_desktop_context_menu(event.globalPos())
        event.accept()

    def _show_desktop_context_menu(self, global_pos: QPoint) -> None:
        if not self.desktop_mode:
            return
        self._build_desktop_context_menu().exec(global_pos)

    def _show_desktop_status_panel(self) -> None:
        QMessageBox.information(
            self,
            "状态面板",
            self._format_desktop_status_panel(self.controller.get_snapshot()),
        )

    def _show_dialogue_history_panel(self) -> None:
        history_text = self.controller.copy_dialogue_history_text() or "暂无对话历史"
        QMessageBox.information(self, "对话历史", history_text)

    def _clear_dialogue_history(self) -> None:
        self._apply_snapshot(self.controller.clear_dialogue_history())
        self.desktop_feedback_label.show()

    def _copy_dialogue_history_to_clipboard(self) -> None:
        history_text = self.controller.copy_dialogue_history_text()
        QApplication.clipboard().setText(history_text)
        if not history_text:
            self.desktop_feedback_label.setText(f"{self.controller.state.character_name}：暂无可复制的对话。")
        else:
            self.desktop_feedback_label.setText(f"{self.controller.state.character_name}：对话已复制。")
        self.desktop_feedback_label.show()

    def _replay_latest_dialogue(self) -> None:
        self._apply_snapshot(self.controller.replay_latest_dialogue())
        self.desktop_feedback_label.show()

    def _revert_dialogue_history(self) -> None:
        self._apply_snapshot(self.controller.revert_dialogue_history())
        self.desktop_feedback_label.show()

    def _format_desktop_status_panel(self, snapshot: dict[str, object]) -> str:
        return (
            f"模式：{snapshot['mode']}\n"
            f"能量 {int(float(snapshot['charge']))} / 心情 {int(float(snapshot['mood']))} / "
            f"信任 {int(float(snapshot['trust']))}\n"
            f"动作：{snapshot['motion_caption']}\n"
            f"{snapshot['feedback']}"
        )

    def _return_to_control_panel(self) -> None:
        if not self.desktop_mode:
            return
        if self._return_target_window is not None:
            self._return_target_window.show()
            self._return_target_window.raise_()
            self._return_target_window.activateWindow()
            self.close()
            return
        self.desktop_mode = False
        flags = self.windowFlags()
        flags &= ~Qt.WindowType.FramelessWindowHint
        flags &= ~Qt.WindowType.WindowStaysOnTopHint
        flags &= ~Qt.WindowType.NoDropShadowWindowHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        for widget in (self.root_widget, self.hero_card, self.sprite_label):
            widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
            widget.setAutoFillBackground(False)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(MAX_QT_WIDGET_SIZE, MAX_QT_WIDGET_SIZE)
        self.root_widget.setStyleSheet("")
        self.shell_layout.setContentsMargins(0, 0, 0, 0)
        self.shell_layout.setSpacing(0)
        self.control_panel_content_layout.setContentsMargins(16, 16, 16, 16)
        self.control_panel_content_layout.setSpacing(12)
        for page_layout in self.control_panel_page_layouts:
            page_layout.setSpacing(12)
        self.launcher_card.show()
        self.sidebar_card.show()
        for card in (
            self.status_card,
            self.feedback_card,
            self.actions_card,
            self.demo_card,
            self.perception_card,
            self.shop_card,
            self.inventory_card,
        ):
            card.show()
        self.hero_card.setTitle("角色动画区")
        self.hero_card.setStyleSheet("")
        self.hero_layout.setContentsMargins(9, 9, 9, 9)
        self.hero_layout.setSpacing(6)
        self.character_label.show()
        self.sprite_label.setMaximumSize(MAX_QT_WIDGET_SIZE, MAX_QT_WIDGET_SIZE)
        self.sprite_label.setMinimumSize(0, CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        self.sprite_label.setMinimumHeight(CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        self.sprite_label.setStyleSheet(CONTROL_PANEL_SPRITE_STYLE)
        self.clearMask()
        self.desktop_feedback_label.hide()
        self.dialogue_bar.hide()
        self.resize(1180, 760)
        self.show()
        self._apply_snapshot(self.controller.get_snapshot())

    def _move_desktop_window_by(self, delta: QPoint) -> None:
        if not self.desktop_mode:
            return
        self.move(self._clamp_desktop_position(self.pos() + delta))

    def _clamp_desktop_position(self, target: QPoint) -> QPoint:
        bounds = self._desktop_available_geometry()
        max_x = max(bounds.left(), bounds.right() - self.width() + 1)
        max_y = max(bounds.top(), bounds.bottom() - self.height() + 1)
        x = min(max(target.x(), bounds.left()), max_x)
        y = min(max(target.y(), bounds.top()), max_y)
        return QPoint(x, y)

    def _dock_desktop_position(self, target: QPoint) -> QPoint:
        clamped = self._clamp_desktop_position(target)
        bounds = self._desktop_available_geometry()
        max_x = max(bounds.left(), bounds.right() - self.width() + 1)
        max_y = max(bounds.top(), bounds.bottom() - self.height() + 1)

        x = clamped.x()
        if x - bounds.left() <= DESKTOP_DOCK_THRESHOLD_PX:
            x = bounds.left()
        elif max_x - x <= DESKTOP_DOCK_THRESHOLD_PX:
            x = max_x

        y = clamped.y()
        if y - bounds.top() <= DESKTOP_DOCK_THRESHOLD_PX:
            y = bounds.top()
        elif max_y - y <= DESKTOP_DOCK_THRESHOLD_PX:
            y = max_y

        return QPoint(x, y)

    def _desktop_available_geometry(self) -> QRect:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return QRect(self.pos(), self.size())
        return screen.availableGeometry()

    def _setup_timers(self) -> None:
        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self._advance_frame)
        self.frame_timer.start(self.motion_animator.interval_ms())

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._handle_tick)
        if self._advance_ticks:
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
        if self.desktop_mode and action_id == "drag":
            self.move(self._dock_desktop_position(self.pos()))
        self._apply_snapshot(self.controller.perform_action(action_id, include_ai_expression=False))

    @Slot()
    def _handle_dialogue_submit(self) -> None:
        request = DialogueRequest(text=self.dialogue_input.text())
        snapshot = self.controller.submit_dialogue_request(request, include_ai_expression=False)
        self.dialogue_input.clear()
        self._apply_snapshot(snapshot)
        self.desktop_feedback_label.show()

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
            f"金币 {snapshot['coins']} / 等级 {snapshot['level']} / 经验 {snapshot['exp']}"
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
        self.events_label.setText(self._format_event_summary(snapshot["events"]))
        self.memory_label.setText(self._format_memory_log(snapshot["memory_log"]))
        self.desktop_feedback_label.setText(f"{snapshot['character_name']}：{snapshot['feedback']}")

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
        if self.desktop_mode:
            self.clearMask()

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

    def _format_event_summary(self, events: object) -> str:
        if not isinstance(events, list) or not events:
            return "最近事件：暂无"
        lines: list[str] = []
        for event in events[:3]:
            if not isinstance(event, dict):
                continue
            character_name = str(event.get("character_name", ""))
            speech = str(event.get("speech", "")).strip()
            if not speech:
                continue
            if character_name == "STAT":
                lines.append(f"状态：{speech}")
            elif character_name == "CHOICE":
                lines.append(f"可选动作：{speech}")
            elif character_name:
                lines.append(f"{character_name}：{speech}")
        return "\n".join(lines) if lines else "最近事件：暂无"

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
    configure_application_style(app)
    controller = CompanionController(save_path=DEMO_SAVE_PATH) if should_use_demo_save(args) else CompanionController()
    if should_reset_demo_save(args):
        controller.reset_demo_state(include_ai_expression=False)
    window = CompanionWindow(controller=controller, desktop_mode=should_use_desktop_mode(args))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(launch())
