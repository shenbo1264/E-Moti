from __future__ import annotations

import json
import sys

from collections.abc import Callable

from PySide6.QtCore import QEvent, QPoint, QSize, QTimer, Qt, Slot
from PySide6.QtGui import QAction, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QStyleFactory,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .ai_expressor import build_expression_prompt_preview
from .capability_runtime import CapabilityRuntime
from .capability_panels import CapabilitySettingsPanel, ManualPerceptionPanel, VoiceSettingsPanel
from .capability_settings import CapabilitySettings
from .character_registry import CharacterPackSummary, CharacterRegistry
from .controller import CompanionController
from .dialogue import DialogueRequest
from .desktop_shell import DesktopShell
from .expression_settings import (
    EXPRESSION_PROVIDER_PRESETS,
    normalize_expression_settings,
    provider_default_base_url,
    provider_default_model,
)
from .expression_context import ExpressionContextChain, ManualPerceptionExpressionContextProvider
from .motion import MotionAnimator, load_motion_catalog_from_dir
from .live2d_web import Live2DWebSurface, has_safe_live2d_model
from .presentation_renderer import (
    Live2DWebPresentationAdapter,
    PortraitPresentationAdapter,
    PresentationFrame,
    SpritePresentationAdapter,
)
from .screen_observation import ScreenObservationService
from .snapshot_renderer import SnapshotRenderer
from .spirit_stage import SpiritStageSurface, has_safe_portrait_manifest, load_portrait_manifest
from .storage import DEMO_SAVE_PATH
from .tray_controller import TrayController
from .voice_asr import ASRService
from .voice_tts import TTSManager
from .web_search import WebSearchService

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


def _presentation_renderer_from_profile(renderer_profile, asset_dir):
    if (
        renderer_profile.backend == "portrait"
        and renderer_profile.portrait_manifest
        and has_safe_portrait_manifest(asset_dir, renderer_profile.portrait_manifest)
    ):
        manifest = load_portrait_manifest(asset_dir, renderer_profile.portrait_manifest)
        return PortraitPresentationAdapter(
            portrait_manifest=renderer_profile.portrait_manifest,
            expression_map=renderer_profile.expression_map,
            fallback_expression=manifest.fallback_expression,
        )
    if (
        renderer_profile.backend == "live2d_web"
        and renderer_profile.model
        and has_safe_live2d_model(asset_dir, renderer_profile.model)
    ):
        return Live2DWebPresentationAdapter(
            model_path=renderer_profile.model,
            motion_map=renderer_profile.motion_map,
            expression_map=renderer_profile.expression_map,
        )
    return SpritePresentationAdapter(motion_map=renderer_profile.motion_map)


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
        self.screen_observation_service = ScreenObservationService()
        self.screen_observation_timer = QTimer(self)
        self.screen_observation_timer.timeout.connect(self._run_screen_observation)
        self.web_search_service = WebSearchService()
        self.tts_manager = TTSManager()
        self.asr_service = ASRService()
        self.capability_runtime = CapabilityRuntime(
            settings_saver=self._save_capability_settings_from_ui,
            settings_reader=self.controller.get_capability_settings,
            set_perception_summary=self.controller.set_perception_summary,
            set_tool_results=self.controller.set_tool_results,
            screen_observation_service=lambda: self.screen_observation_service,
            web_search_service=lambda: self.web_search_service,
            tts_manager=lambda: self.tts_manager,
            asr_service=lambda: self.asr_service,
        )
        self._last_auto_tts_key: tuple[str, str] | None = None
        self.desktop_pet_window: CompanionWindow | None = None
        self._return_target_window: CompanionWindow | None = None
        self._close_callbacks: list[Callable[[CompanionWindow], None]] = []
        self.snapshot_renderer = SnapshotRenderer()
        self.presentation_renderer = _presentation_renderer_from_profile(
            self.controller.character_pack.renderer,
            self.controller.resources.asset_dir,
        )
        user_pack_root = (
            self.controller.user_data_root / "character_packs"
            if self.controller.user_data_root is not None
            else None
        )
        self.character_registry = CharacterRegistry(
            builtin_root=self.controller.resources.asset_dir.parent,
            user_root=user_pack_root,
        )
        self.motion_catalog = load_motion_catalog_from_dir(self.controller.resources.asset_dir)
        self.motion_animator = MotionAnimator(self.motion_catalog)
        self.spritesheet = QPixmap(str(self.motion_catalog.sheet_path))
        self.desktop_shell = DesktopShell(self, dock_threshold_px=DESKTOP_DOCK_THRESHOLD_PX)
        self.tray_controller = TrayController(
            parent=self,
            tray_icon_class=QSystemTrayIcon,
            icon_provider=self._build_tray_icon,
            show_control_panel=self._show_control_panel_from_tray,
            show_desktop_pet=self._show_desktop_pet_from_tray,
            hide_window=self.hide,
            close_window=self.close,
            application_provider=QApplication.instance,
        )
        self.remaining_seconds = 15
        self.action_buttons: dict[str, QPushButton] = {}
        self.navigation_buttons: list[QPushButton] = []
        self.status_bars: dict[str, QProgressBar] = {}
        self.stat_name_labels: list[QLabel] = []
        self._manual_perception_summary = ""
        self._base_expression_context_provider = self.controller.expression_context_provider
        self._manual_expression_context_provider = self.controller.expression_context_provider
        self._install_manual_expression_context_provider()

        configure_application_style(QApplication.instance())
        self.setWindowTitle("星汐 E-Moti 桌面伴侣")
        self.resize(1180, 760)
        self._build_ui()
        if self.desktop_mode:
            self._apply_desktop_mode()
        self._setup_timers()
        self._apply_snapshot(self.controller.get_snapshot())
        self.tray_controller.setup(owns_controller=self._owns_controller)

    def _install_manual_expression_context_provider(self) -> None:
        current_provider = self.controller.expression_context_provider
        if current_provider is self._manual_expression_context_provider:
            current_provider = self._base_expression_context_provider
        self._base_expression_context_provider = current_provider
        self._manual_expression_context_provider = ExpressionContextChain(
            [self._base_expression_context_provider, self._manual_perception_context]
        )
        self.controller.expression_context_provider = self._manual_expression_context_provider

    def _register_close_callback(self, callback: Callable[["CompanionWindow"], None]) -> None:
        self._close_callbacks.append(callback)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if (
            event.type() == QEvent.Type.WindowStateChange
            and self.isMinimized()
            and self.tray_controller.should_hide_to_tray()
        ):
            QTimer.singleShot(0, self.tray_controller.hide_to_tray)

    def closeEvent(self, event) -> None:
        if self.tray_controller.should_hide_to_tray():
            event.ignore()
            self.tray_controller.hide_to_tray()
            return
        pet_window = self.desktop_pet_window
        if pet_window is not None:
            self.desktop_pet_window = None
            pet_window.close()
        self.tray_controller.cleanup()
        self.frame_timer.stop()
        self.tick_timer.stop()
        self.countdown_timer.stop()
        self.screen_observation_timer.stop()
        self._manual_perception_summary = ""
        if self.controller.expression_context_provider is self._manual_expression_context_provider:
            self.controller.expression_context_provider = self._base_expression_context_provider
        try:
            if self._owns_controller:
                self.controller.close()
        except Exception:
            pass
        finally:
            self.tray_controller.restore_quit_on_last_window_closed()
            super().closeEvent(event)
            for callback in tuple(self._close_callbacks):
                callback(self)

    def _build_tray_icon(self) -> QIcon:
        pixmap = self.spritesheet.copy(self.motion_animator.current_frame_rect())
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                QSize(64, 64),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return QIcon(pixmap)

    def _show_control_panel_from_tray(self) -> None:
        if self.desktop_mode:
            self._return_to_control_panel()
            return
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _show_desktop_pet_from_tray(self) -> None:
        if self.desktop_mode:
            self.show()
            self.raise_()
            self.activateWindow()
            return
        self._enter_desktop_mode()

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

        self.character_library_page = self._build_character_library_page()
        self.content_stack.addWidget(self.character_library_page)

        self.capability_settings_panel = CapabilitySettingsPanel(self.controller.get_capability_settings())
        self.capability_settings_panel.saveRequested.connect(self._save_capability_settings_from_ui)
        self.capability_settings_panel.screenObservationRequested.connect(self._run_screen_observation)
        self.capability_settings_panel.webSearchRequested.connect(self._run_web_search)
        self._alias_capability_settings_panel_widgets()
        self.perception_search_page = self.capability_settings_panel
        self.perception_search_layout = self.capability_settings_panel.perception_search_layout
        self.control_panel_page_layouts.append(self.perception_search_layout)
        self.content_stack.addWidget(self.perception_search_page)

        privacy_page = QWidget()
        privacy_layout = QVBoxLayout(privacy_page)
        privacy_layout.setContentsMargins(0, 0, 0, 0)
        privacy_layout.setSpacing(12)
        self.control_panel_page_layouts.append(privacy_layout)
        self.perception_card = ManualPerceptionPanel()
        self.perception_card.manualPerceptionRequested.connect(self._handle_manual_screen_perception)
        self._alias_manual_perception_panel_widgets()
        privacy_layout.addWidget(self.perception_card)
        privacy_layout.addStretch(1)
        self.content_stack.addWidget(privacy_page)

        expression_page = QWidget()
        expression_layout = QVBoxLayout(expression_page)
        expression_layout.setContentsMargins(0, 0, 0, 0)
        expression_layout.setSpacing(12)
        self.control_panel_page_layouts.append(expression_layout)
        self.expression_settings_card = self._build_expression_settings_card()
        expression_layout.addWidget(self.expression_settings_card)
        expression_layout.addStretch(1)
        self.content_stack.addWidget(expression_page)

        rule_page = QWidget()
        rule_layout = QVBoxLayout(rule_page)
        rule_layout.setContentsMargins(0, 0, 0, 0)
        rule_layout.setSpacing(12)
        self.control_panel_page_layouts.append(rule_layout)
        self.expression_rule_card = self._build_expression_rule_card()
        rule_layout.addWidget(self.expression_rule_card)
        rule_layout.addStretch(1)
        self.content_stack.addWidget(rule_page)

        voice_page = QWidget()
        voice_layout = QVBoxLayout(voice_page)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(12)
        self.control_panel_page_layouts.append(voice_layout)
        self.voice_settings_card = VoiceSettingsPanel(
            self.controller.get_capability_settings(),
            self.controller.get_expression_settings(),
        )
        self.voice_settings_card.ttsTestRequested.connect(self._handle_tts_test)
        self.voice_settings_card.ttsStopRequested.connect(self._handle_tts_stop)
        self.voice_settings_card.asrStartRequested.connect(self._handle_asr_start)
        self.voice_settings_card.asrStopRequested.connect(self._handle_asr_stop)
        self._alias_voice_settings_panel_widgets()
        voice_layout.addWidget(self.voice_settings_card)
        voice_layout.addStretch(1)
        self.content_stack.addWidget(voice_page)
        self._load_capability_settings_into_ui()

    def _alias_capability_settings_panel_widgets(self) -> None:
        for name in (
            "screen_observation_settings_card",
            "screen_observation_enabled_check",
            "screen_observation_auto_check",
            "screen_observation_interval_input",
            "screen_observation_max_width_input",
            "screen_observation_model_input",
            "screen_observation_base_url_input",
            "screen_observation_api_key_input",
            "screen_observation_run_button",
            "screen_observation_status_label",
            "web_search_settings_card",
            "web_search_enabled_check",
            "web_search_engine_combo",
            "web_search_max_results_input",
            "web_search_query_input",
            "web_search_run_button",
            "web_search_results_label",
            "proactive_companion_settings_card",
            "proactive_companion_enabled_check",
            "proactive_interval_input",
            "proactive_global_cooldown_input",
            "proactive_daily_limit_input",
            "proactive_quiet_hours_check",
            "proactive_quiet_start_input",
            "proactive_quiet_end_input",
            "proactive_allow_context_topic_check",
            "capability_save_button",
            "capability_feedback_label",
        ):
            setattr(self, name, getattr(self.capability_settings_panel, name))

    def _alias_manual_perception_panel_widgets(self) -> None:
        for name in (
            "perception_status_label",
            "perception_privacy_label",
            "observe_screen_button",
        ):
            setattr(self, name, getattr(self.perception_card, name))

    def _alias_voice_settings_panel_widgets(self) -> None:
        for name in (
            "voice_status_label",
            "voice_tts_provider_label",
            "voice_asr_provider_label",
            "tts_enabled_check",
            "tts_provider_combo",
            "tts_api_url_input",
            "tts_model_variant_combo",
            "tts_auto_speak_check",
            "tts_test_button",
            "tts_stop_button",
            "asr_enabled_check",
            "asr_provider_combo",
            "asr_model_input",
            "asr_base_url_input",
            "asr_api_key_input",
            "asr_auto_send_check",
            "asr_start_button",
            "asr_stop_button",
            "voice_tts_enable_button",
            "voice_asr_enable_button",
        ):
            setattr(self, name, getattr(self.voice_settings_card, name))

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

        for index, label in enumerate(("总览", "互动", "背包", "角色库", "感知与搜索", "隐私", "LLM表达", "表达规则", "语音")):
            button = QPushButton(label)
            button.setObjectName("NavigationButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, current=index: self._select_navigation_button(current))
            self.navigation_buttons.append(button)
            layout.addWidget(button)
        self.navigation_buttons[0].setChecked(True)

        layout.addStretch(1)
        return frame

    def _build_character_library_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.control_panel_page_layouts.append(layout)

        list_box = QGroupBox("角色库")
        list_layout = QVBoxLayout(list_box)
        self.character_list = QListWidget()
        self.character_list.currentItemChanged.connect(lambda current, previous=None: self._update_character_detail())
        list_layout.addWidget(self.character_list)
        self.character_refresh_button = QPushButton("刷新角色包")
        self.character_refresh_button.clicked.connect(self._refresh_character_library)
        list_layout.addWidget(self.character_refresh_button)
        layout.addWidget(list_box, stretch=2)

        detail_box = QGroupBox("角色详情")
        detail_layout = QVBoxLayout(detail_box)
        detail_layout.setSpacing(10)
        self.character_preview_label = QLabel()
        self.character_preview_label.setFixedHeight(148)
        self.character_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.character_preview_label.setStyleSheet(
            "QLabel { border: 1px solid #cbdde5; border-radius: 8px; background: #f7fbfd; }"
        )
        self.character_detail_label = QLabel("选择一个角色包。")
        self.character_detail_label.setWordWrap(True)
        self.character_detail_label.setObjectName("CharacterDetailLabel")
        self.character_switch_button = QPushButton("切换到此角色")
        self.character_switch_button.clicked.connect(self._handle_character_switch)
        self.character_import_button = QPushButton("导入角色包")
        self.character_import_button.setEnabled(False)
        self.character_import_button.setToolTip("P4：本地导入角色包，先校验再启用。")
        self.character_generate_button = QPushButton("生成新角色")
        self.character_generate_button.setEnabled(False)
        self.character_generate_button.setToolTip("P5：AI 生成工作流输出到临时目录，人工 QA 后导入。")
        detail_layout.addWidget(self.character_preview_label)
        detail_layout.addWidget(self.character_detail_label)
        detail_layout.addWidget(self.character_switch_button)
        controls = QHBoxLayout()
        controls.addWidget(self.character_import_button)
        controls.addWidget(self.character_generate_button)
        detail_layout.addLayout(controls)
        detail_layout.addStretch(1)
        layout.addWidget(detail_box, stretch=3)

        self._character_pack_summaries: dict[str, CharacterPackSummary] = {}
        self._refresh_character_library()
        return page

    def _select_navigation_button(self, selected_index: int) -> None:
        for index, button in enumerate(self.navigation_buttons):
            button.setChecked(index == selected_index)
        if hasattr(self, "content_stack"):
            self.content_stack.setCurrentIndex(selected_index)

    def _refresh_character_library(self) -> None:
        if not hasattr(self, "character_list"):
            return
        current_id = self._selected_character_id() or self.controller.state.character_id
        self.character_list.clear()
        self._character_pack_summaries = {
            pack.character_id: pack for pack in self.character_registry.list_available_packs()
        }
        for pack in self._character_pack_summaries.values():
            item = QListWidgetItem(f"{pack.name} | {pack.title}")
            item.setData(Qt.ItemDataRole.UserRole, pack.character_id)
            if pack.preview_path.is_file():
                item.setIcon(QIcon(str(pack.preview_path)))
            self.character_list.addItem(item)
            if pack.character_id == current_id:
                self.character_list.setCurrentItem(item)
        if self.character_list.currentItem() is None and self.character_list.count():
            self.character_list.setCurrentRow(0)
        self._update_character_detail()

    def _selected_character_id(self) -> str:
        if not hasattr(self, "character_list"):
            return ""
        item = self.character_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""

    def _update_character_detail(self) -> None:
        character_id = self._selected_character_id()
        pack = self._character_pack_summaries.get(character_id)
        if pack is None:
            self.character_detail_label.setText("没有可用角色包。")
            self.character_preview_label.clear()
            self.character_switch_button.setEnabled(False)
            return
        current = character_id == self.controller.state.character_id
        self.character_detail_label.setText(
            f"{pack.name}\n{pack.title}\n\n{pack.description}\n\n"
            "切换角色会切换外观、语气、商店主题和独立记忆，不改写其他角色会话。"
        )
        if pack.preview_path.is_file():
            preview = QPixmap(str(pack.preview_path))
            self.character_preview_label.setPixmap(
                preview.scaled(
                    220,
                    132,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.character_preview_label.setText("暂无预览")
        self.character_switch_button.setEnabled(not current)
        self.character_switch_button.setText("当前角色" if current else "切换到此角色")

    def _handle_character_switch(self) -> None:
        character_id = self._selected_character_id()
        if not character_id:
            self._show_message("请先选择一个角色。")
            return
        try:
            pack = self._character_pack_summaries.get(character_id)
            snapshot = self.controller.switch_character(
                character_id,
                pack_dir=pack.path if pack is not None else None,
                include_ai_expression=False,
            )
            self._reload_character_assets()
            self._install_manual_expression_context_provider()
            self._sync_linked_character_windows(snapshot)
            self._apply_snapshot(snapshot)
            self._refresh_character_library()
        except (KeyError, ValueError, OSError) as exc:
            self._show_message(str(exc))

    def _sync_linked_character_windows(self, snapshot: dict[str, object]) -> None:
        linked = []
        if self.desktop_pet_window is not None and self.desktop_pet_window is not self:
            linked.append(self.desktop_pet_window)
        if self._return_target_window is not None and self._return_target_window is not self:
            linked.append(self._return_target_window)
        for window in linked:
            window._reload_character_assets()
            window._install_manual_expression_context_provider()
            window._apply_snapshot(snapshot)
            window._refresh_character_library()

    def _reload_character_assets(self) -> None:
        self.motion_catalog = load_motion_catalog_from_dir(self.controller.resources.asset_dir)
        self.motion_animator = MotionAnimator(self.motion_catalog)
        self.spritesheet = QPixmap(str(self.motion_catalog.sheet_path))
        self.presentation_renderer = _presentation_renderer_from_profile(
            self.controller.character_pack.renderer,
            self.controller.resources.asset_dir,
        )

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
            on_drag_move=lambda delta: self.desktop_shell.move_by(delta, enabled=self.desktop_mode),
        )
        self.sprite_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sprite_label.customContextMenuRequested.connect(
            lambda pos: self._show_desktop_context_menu(self.sprite_label.mapToGlobal(pos))
        )
        self.sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite_label.setStyleSheet(CONTROL_PANEL_SPRITE_STYLE)
        self.sprite_label.setMinimumHeight(CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        layout.addWidget(self.sprite_label)
        self.live2d_surface = Live2DWebSurface()
        self.live2d_surface.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.live2d_surface.customContextMenuRequested.connect(
            lambda pos: self._show_desktop_context_menu(self.live2d_surface.mapToGlobal(pos))
        )
        self.live2d_surface.setMinimumHeight(CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        self.live2d_surface.hide()
        layout.addWidget(self.live2d_surface)
        self.spirit_surface = SpiritStageSurface()
        self.spirit_surface.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.spirit_surface.customContextMenuRequested.connect(
            lambda pos: self._show_desktop_context_menu(self.spirit_surface.mapToGlobal(pos))
        )
        self.spirit_surface.setMinimumHeight(CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        self.spirit_surface.hide()
        layout.addWidget(self.spirit_surface)
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
        self.dialogue_asr_button = QPushButton("Mic")
        self.dialogue_asr_button.setObjectName("DialogueAsrButton")
        self.dialogue_asr_button.setToolTip("ASR 服务接入后用于语音输入")
        self.dialogue_asr_button.setMinimumHeight(30)
        self.dialogue_asr_button.setEnabled(False)
        dialogue_layout.addWidget(self.dialogue_input, stretch=1)
        dialogue_layout.addWidget(self.dialogue_asr_button)
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
        alias_row = QHBoxLayout()
        self.player_alias_input = QLineEdit()
        self.player_alias_input.setPlaceholderText("本地称呼")
        self.player_alias_save_button = QPushButton("记住称呼")
        self.player_alias_save_button.clicked.connect(self._handle_player_alias_save)
        alias_row.addWidget(self.player_alias_input, stretch=1)
        alias_row.addWidget(self.player_alias_save_button)
        layout.addLayout(alias_row)

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

    def _build_expression_settings_card(self) -> QGroupBox:
        box = QGroupBox("LLM 表达接入")
        layout = QGridLayout(box)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        settings = self.controller.get_expression_settings(include_api_key=True)
        self.expression_enabled_checkbox = QCheckBox("启用 LLM 表达增强")
        self.expression_enabled_checkbox.setChecked(bool(settings["enabled"]))

        self.expression_provider_combo = QComboBox()
        self.expression_provider_combo.addItems(list(EXPRESSION_PROVIDER_PRESETS))
        provider_index = self.expression_provider_combo.findText(str(settings["provider"]))
        self.expression_provider_combo.setCurrentIndex(max(0, provider_index))
        self.expression_provider_combo.currentTextChanged.connect(self._handle_expression_provider_change)

        self.expression_model_input = QLineEdit(str(settings["model"]))
        self.expression_model_input.setPlaceholderText("例如 gpt-5.5")
        self.expression_model_fetch_button = QPushButton("获取模型列表")
        self.expression_model_fetch_button.clicked.connect(self._handle_expression_model_fetch)
        self.expression_model_list_combo = QComboBox()
        self.expression_model_list_combo.setEnabled(False)
        self.expression_model_list_combo.hide()
        self.expression_model_list_combo.currentTextChanged.connect(self._handle_expression_model_selected)
        self.expression_base_url_input = QLineEdit(str(settings["base_url"]))
        self.expression_base_url_input.setPlaceholderText("OpenAI-compatible Base URL 或完整 endpoint")
        self.expression_api_key_input = QLineEdit(str(settings["api_key"]))
        self.expression_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.expression_api_key_input.setPlaceholderText("粘贴 API Key")
        self.expression_timeout_input = QDoubleSpinBox()
        self.expression_timeout_input.setRange(0.1, 60.0)
        self.expression_timeout_input.setDecimals(2)
        self.expression_timeout_input.setSingleStep(0.1)
        self.expression_timeout_input.setValue(float(settings["timeout_seconds"]))
        self.expression_save_button = QPushButton("保存表达设置")
        self.expression_save_button.clicked.connect(self._handle_expression_settings_save)
        self.expression_test_button = QPushButton("测试 LLM 回应")
        self.expression_test_button.clicked.connect(self._handle_expression_settings_test)
        self.expression_settings_status_label = QLabel("LLM 表达：关闭" if not settings["enabled"] else "LLM 表达：已启用")
        self.expression_settings_status_label.setWordWrap(True)
        self.expression_provider_label = QLabel("服务商")
        self.expression_model_label = QLabel("模型 ID")
        self.expression_base_url_label = QLabel("Base URL")
        self.expression_api_key_label = QLabel("API Key")
        self.expression_timeout_label = QLabel("超时（秒）")

        layout.addWidget(self.expression_enabled_checkbox, 0, 0, 1, 2)
        layout.addWidget(self.expression_provider_label, 1, 0)
        layout.addWidget(self.expression_provider_combo, 1, 1, 1, 2)
        layout.addWidget(self.expression_model_label, 2, 0)
        layout.addWidget(self.expression_model_input, 2, 1)
        layout.addWidget(self.expression_model_fetch_button, 2, 2)
        layout.addWidget(self.expression_model_list_combo, 3, 1, 1, 2)
        layout.addWidget(self.expression_base_url_label, 4, 0)
        layout.addWidget(self.expression_base_url_input, 4, 1, 1, 2)
        layout.addWidget(self.expression_api_key_label, 5, 0)
        layout.addWidget(self.expression_api_key_input, 5, 1, 1, 2)
        layout.addWidget(self.expression_timeout_label, 6, 0)
        layout.addWidget(self.expression_timeout_input, 6, 1, 1, 2)
        layout.addWidget(self.expression_save_button, 7, 0)
        layout.addWidget(self.expression_test_button, 7, 1, 1, 2)
        layout.addWidget(self.expression_settings_status_label, 8, 0, 1, 3)
        return box

    def _build_expression_rule_card(self) -> QGroupBox:
        box = QGroupBox("表达规则")
        layout = QVBoxLayout(box)
        self.expression_rule_preview_text = QTextEdit()
        self.expression_rule_preview_text.setReadOnly(True)
        self.expression_rule_preview_text.setPlainText(
            build_expression_prompt_preview(character_name=self.controller.state.character_name)
        )
        self.expression_rule_preview_text.setMinimumHeight(220)
        self.expression_rule_copy_button = QPushButton("复制规则")
        self.expression_rule_copy_button.clicked.connect(self._handle_expression_rule_copy)
        self.expression_rule_status_label = QLabel("表达规则：只读")
        layout.addWidget(self.expression_rule_preview_text)
        layout.addWidget(self.expression_rule_copy_button)
        layout.addWidget(self.expression_rule_status_label)
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
        self.screen_observation_timer.stop()
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        for widget in (self.root_widget, self.hero_card, self.sprite_label, self.live2d_surface, self.spirit_surface):
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
        self.screen_observation_settings_card.hide()
        self.web_search_settings_card.hide()
        self.proactive_companion_settings_card.hide()
        self.perception_card.hide()
        self.expression_settings_card.hide()
        self.expression_rule_card.hide()
        self.voice_settings_card.hide()
        self.shop_card.hide()
        self.inventory_card.hide()
        self.hero_card.setTitle("")
        self.hero_card.setStyleSheet(DESKTOP_HERO_STYLE)
        self.hero_layout.setContentsMargins(0, 0, 0, 0)
        self.hero_layout.setSpacing(6)
        self.hero_layout.setAlignment(self.sprite_label, Qt.AlignmentFlag.AlignHCenter)
        self.hero_layout.setAlignment(self.live2d_surface, Qt.AlignmentFlag.AlignHCenter)
        self.hero_layout.setAlignment(self.spirit_surface, Qt.AlignmentFlag.AlignHCenter)
        self.hero_layout.setAlignment(self.desktop_feedback_label, Qt.AlignmentFlag.AlignHCenter)
        self.hero_layout.setAlignment(self.dialogue_bar, Qt.AlignmentFlag.AlignHCenter)
        self.character_label.hide()
        self.desktop_feedback_label.hide()
        self.dialogue_bar.show()
        self.item_feedback_label.hide()
        self.sprite_label.setStyleSheet(DESKTOP_SPRITE_STYLE)
        self.sprite_label.setFixedSize(DESKTOP_SPRITE_WIDTH, DESKTOP_SPRITE_HEIGHT)
        self.live2d_surface.setStyleSheet(DESKTOP_SPRITE_STYLE)
        self.live2d_surface.setFixedSize(DESKTOP_SPRITE_WIDTH, DESKTOP_SPRITE_HEIGHT)
        self.spirit_surface.setStyleSheet(DESKTOP_SPRITE_STYLE)
        self.spirit_surface.setFixedSize(DESKTOP_SPRITE_WIDTH, DESKTOP_SPRITE_HEIGHT)
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
        exit_action.triggered.connect(self.tray_controller.request_quit)
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
            self.snapshot_renderer.format_desktop_status_panel(self.controller.get_snapshot()),
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
        for widget in (self.root_widget, self.hero_card, self.sprite_label, self.live2d_surface, self.spirit_surface):
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
            self.screen_observation_settings_card,
            self.web_search_settings_card,
            self.proactive_companion_settings_card,
            self.perception_card,
            self.expression_settings_card,
            self.expression_rule_card,
            self.voice_settings_card,
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
        self.live2d_surface.setMaximumSize(MAX_QT_WIDGET_SIZE, MAX_QT_WIDGET_SIZE)
        self.live2d_surface.setMinimumSize(0, CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        self.live2d_surface.setMinimumHeight(CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        self.spirit_surface.setMaximumSize(MAX_QT_WIDGET_SIZE, MAX_QT_WIDGET_SIZE)
        self.spirit_surface.setMinimumSize(0, CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        self.spirit_surface.setMinimumHeight(CONTROL_PANEL_SPRITE_MIN_HEIGHT)
        self.clearMask()
        self.desktop_feedback_label.hide()
        self.dialogue_bar.hide()
        self.resize(1180, 760)
        self.show()
        self._apply_snapshot(self.controller.get_snapshot())
        self._update_screen_observation_timer()

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
        if self.presentation_renderer.backend != "sprite":
            return
        self.motion_animator.advance()
        self._render_current_frame()

    def _handle_action(self, action_id: str) -> None:
        if self.desktop_mode and action_id == "drag":
            self.move(self.desktop_shell.dock_position(self.pos()))
        self._apply_snapshot(self.controller.perform_action(action_id, include_ai_expression=False))

    @Slot()
    def _handle_dialogue_submit(self) -> None:
        text = self.dialogue_input.text().strip()
        if text.startswith("/search "):
            query = text[len("/search ") :].strip()
            self.dialogue_input.clear()
            self._run_web_search(query)
            return
        request = DialogueRequest(text=text)
        snapshot = self.controller.submit_dialogue_request(
            request,
            include_ai_expression=self._llm_expression_enabled(),
        )
        self.dialogue_input.clear()
        self._apply_snapshot(snapshot)
        self.desktop_feedback_label.show()

    def _handle_player_alias_save(self) -> None:
        snapshot = self.controller.set_player_alias(
            self.player_alias_input.text(),
            include_ai_expression=False,
        )
        self._apply_snapshot(snapshot)

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

    def _run_screen_observation(self) -> None:
        result = self.capability_runtime.run_screen_observation()
        if result.summary:
            self.screen_observation_status_label.setText(f"{result.message}：{result.summary}")
            return
        self.screen_observation_status_label.setText(result.message)

    def _run_web_search_from_ui(self) -> None:
        self._run_web_search(self.web_search_query_input.text())

    def _run_web_search(self, query: str) -> None:
        result = self.capability_runtime.run_web_search(query)
        self.web_search_results_label.setText(result.display_text)

    def _update_screen_observation_timer(self) -> None:
        settings = self.controller.get_capability_settings().screen_observation
        if self.desktop_mode or not settings.enabled or not settings.auto_enabled:
            self.screen_observation_timer.stop()
            return
        self.screen_observation_timer.start(settings.interval_seconds * 1000)

    def _handle_tts_test(self) -> None:
        result = self.capability_runtime.run_tts_test("星汐在这里，语音测试正常。")
        self.voice_status_label.setText(result.message)

    def _handle_tts_stop(self) -> None:
        result = self.capability_runtime.stop_tts()
        self.voice_status_label.setText(result.message)

    def _sync_voice_controls_enabled(self) -> None:
        self.voice_settings_card.sync_controls_enabled()
        self.dialogue_asr_button.setEnabled(False)

    def _handle_asr_start(self) -> None:
        result = self.capability_runtime.start_asr()
        self.voice_status_label.setText(result.message)

    def _handle_asr_stop(self) -> None:
        result = self.capability_runtime.stop_asr()
        self.voice_status_label.setText(result.message)
        if not result.text:
            return
        self.dialogue_input.setText(result.text)
        if result.dialogue_request is not None:
            snapshot = self.controller.submit_dialogue_request(
                result.dialogue_request,
                include_ai_expression=self._llm_expression_enabled(),
            )
            self.dialogue_input.clear()
            self._apply_snapshot(snapshot)
            self.desktop_feedback_label.show()

    def _handle_expression_settings_save(self) -> None:
        self._save_expression_settings_from_form()
        self.expression_settings_status_label.setText("LLM 表达设置已保存")

    def _handle_expression_settings_test(self) -> None:
        self._save_expression_settings_from_form()
        result = self.controller.test_expression_provider()
        if result["ok"]:
            self.expression_settings_status_label.setText(
                f"LLM 测试通过：{result['speech']}（{self._format_expression_diagnostic_target(result)}）"
            )
            return
        stage = self._format_expression_test_stage(str(result.get("stage", "")))
        reason = self._format_expression_test_failure(str(result.get("reason", result.get("fallback_reason", ""))))
        self.expression_settings_status_label.setText(
            f"LLM 测试失败：{stage} / {reason}（{self._format_expression_diagnostic_target(result)}）"
        )

    def _handle_expression_provider_change(self, provider: str) -> None:
        normalized_provider = str(provider).strip()
        if normalized_provider not in EXPRESSION_PROVIDER_PRESETS:
            return
        self.expression_model_input.setText(provider_default_model(normalized_provider))
        self.expression_base_url_input.setText(provider_default_base_url(normalized_provider))
        self.expression_model_list_combo.clear()
        self.expression_model_list_combo.setEnabled(False)
        self.expression_model_list_combo.hide()
        self.expression_settings_status_label.setText(f"已切换到 {normalized_provider}，请填写 API Key 后保存或测试")

    def _handle_expression_model_fetch(self) -> None:
        try:
            models = self.controller.fetch_expression_models(self._expression_settings_payload_from_form())
        except Exception as exc:
            reason = self._format_expression_test_failure(_model_fetch_reason(exc))
            self.expression_model_list_combo.clear()
            self.expression_model_list_combo.setEnabled(False)
            self.expression_model_list_combo.hide()
            self.expression_settings_status_label.setText(f"模型列表获取失败：{reason}")
            return
        blocked = self.expression_model_list_combo.blockSignals(True)
        self.expression_model_list_combo.clear()
        self.expression_model_list_combo.addItems(list(models))
        self.expression_model_list_combo.setEnabled(True)
        self.expression_model_list_combo.show()
        current_model = self.expression_model_input.text().strip()
        if current_model in models:
            self.expression_model_list_combo.setCurrentText(current_model)
        else:
            self.expression_model_list_combo.setCurrentIndex(0)
            self.expression_model_input.setText(str(models[0]))
        self.expression_model_list_combo.blockSignals(blocked)
        self.expression_settings_status_label.setText(f"获取到 {len(models)} 个模型")

    def _handle_expression_model_selected(self, model: str) -> None:
        if model:
            self.expression_model_input.setText(model)

    def _save_expression_settings_from_form(self) -> dict[str, object]:
        settings = normalize_expression_settings(self._expression_settings_payload_from_form())
        public_settings = self.controller.update_expression_settings(settings)
        self.expression_model_input.setText(str(public_settings["model"]))
        self.expression_base_url_input.setText(str(public_settings["base_url"]))
        self.expression_timeout_input.setValue(float(public_settings["timeout_seconds"]))
        return public_settings

    def _expression_settings_payload_from_form(self) -> dict[str, object]:
        return {
            "enabled": self.expression_enabled_checkbox.isChecked(),
            "provider": self.expression_provider_combo.currentText(),
            "model": self.expression_model_input.text(),
            "base_url": self.expression_base_url_input.text(),
            "api_key": self.expression_api_key_input.text(),
            "timeout_seconds": self.expression_timeout_input.value(),
        }

    def _llm_expression_enabled(self) -> bool:
        return bool(self.controller.get_expression_settings().get("enabled"))

    def _save_capability_settings_from_ui(self) -> CapabilitySettings:
        base = self.controller.get_capability_settings()
        settings = self.capability_settings_panel.collect_settings(base)
        settings = self.voice_settings_card.collect_settings(settings)
        saved = self.controller.update_capability_settings(settings)
        self._load_capability_settings_into_ui(saved)
        self.capability_settings_panel.set_feedback("能力设置已保存")
        return saved

    def _load_capability_settings_into_ui(self, settings: CapabilitySettings | None = None) -> None:
        settings = settings or self.controller.get_capability_settings()
        self.capability_settings_panel.load_settings(settings)
        self.voice_settings_card.load_settings(settings, self.controller.get_expression_settings())
        self.dialogue_asr_button.setEnabled(False)
        self._sync_voice_controls_enabled()
        self._update_screen_observation_timer()

    def _set_combo_current_text(self, combo: QComboBox, value: str) -> None:
        index = combo.findText(value)
        if index < 0 and value:
            combo.addItem(value)
            index = combo.findText(value)
        combo.setCurrentIndex(max(0, index))

    def _format_expression_test_failure(self, reason: str) -> str:
        labels = {
            "disabled": "未启用或缺少 API Key",
            "missing_api_key": "缺少 API Key",
            "local_fallback": "已回退到本地表达",
            "timeout": "请求超时",
            "provider_error": "Provider 调用失败",
            "invalid_json": "返回不是合法 JSON",
            "invalid_response_text": "返回文本为空或过长",
            "invalid_response_json": "返回不是合法 JSON",
            "invalid_response_shape": "返回结构不符合模型列表格式",
            "invalid_payload": "返回内容为空或格式不符合规则",
            "empty_model_list": "模型列表为空",
            "unsafe_event": "返回包含不允许的字段",
            "invalid_event": "返回事件未通过本地校验",
            "too_many_events": "返回事件过多",
            "closed": "表达器已关闭",
        }
        return labels.get(reason, reason or "未知错误")

    def _format_expression_test_stage(self, stage: str) -> str:
        labels = {
            "settings": "设置检查",
            "model_list": "模型列表",
            "prompt": "构造提示",
            "provider_call": "调用服务",
            "provider_parse": "解析响应",
            "event_validation": "事件校验",
        }
        return labels.get(stage, stage or "未知阶段")

    def _format_expression_diagnostic_target(self, result: dict[str, object]) -> str:
        provider = str(result.get("provider", "") or "unknown")
        model = str(result.get("model", "") or "unknown")
        timeout = result.get("timeout_seconds", "")
        if timeout == "":
            return f"{provider}/{model}"
        return f"{provider}/{model}，超时 {timeout}s"

    def _handle_expression_rule_copy(self) -> None:
        text = self.expression_rule_preview_text.toPlainText()
        QApplication.clipboard().setText(text)
        self.expression_rule_status_label.setText("表达规则已复制")

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
        frame = self.presentation_renderer.frame_from_snapshot(snapshot)
        if frame.backend == "portrait":
            self._render_portrait_frame(frame)
        elif frame.backend == "live2d_web":
            self._render_live2d_frame(frame)
        else:
            self.motion_animator.set_motion(frame.motion)
            self.frame_timer.setInterval(self.motion_animator.interval_ms())
            self._render_current_frame()
        self.character_label.setText(
            f"{snapshot['character_name']}\n{snapshot['character_title']}\n\n"
            f"模式：{snapshot['mode']}\n"
            f"动作：{snapshot['motion_caption']}\n\n"
            f"{snapshot['character_description']}"
        )
        self.dialogue_input.setPlaceholderText(f"和{snapshot['character_name']}说点什么")
        self.mode_label.setText(f"当前模式：{snapshot['mode']}")
        self.resources_label.setText(
            f"金币 {snapshot['coins']} / 等级 {snapshot['level']} / 经验 {snapshot['exp']}"
        )
        self.goal_label.setText(str(snapshot["goal"]))
        self.relationship_label.setText(self.snapshot_renderer.format_relationship_presentation(snapshot))
        if not self.player_alias_input.hasFocus():
            self.player_alias_input.setText(str(snapshot.get("player_alias") or ""))
        self.tick_label.setText(f"15 秒 tick：已结算 {snapshot['tick_count']} 次，下一轮 {self.remaining_seconds} 秒后")

        for stat_name, bar in self.status_bars.items():
            bar.setValue(int(float(snapshot[stat_name])))

        self.feedback_label.setText(str(snapshot["feedback"]))
        self.delta_label.setText(f"最近变化：{snapshot['delta_text']}")
        self.events_label.setText(self.snapshot_renderer.format_event_summary(snapshot["events"]))
        self.memory_label.setText(self.snapshot_renderer.format_memory_log(snapshot["memory_log"]))
        desktop_speech = self.snapshot_renderer.snapshot_tts_speech(snapshot) or str(snapshot["feedback"])
        self.desktop_feedback_label.setText(str(snapshot["character_name"]) + ": " + desktop_speech)

        actions = {entry["action_id"]: entry for entry in snapshot["actions"]}
        for action_id, button in self.action_buttons.items():
            entry = actions[action_id]
            button.setText(str(entry["label"]))
            button.setEnabled(bool(entry["enabled"]))

        self._fill_list(self.shop_list, snapshot["shop_items"], kind="shop")
        self._fill_list(self.inventory_list, snapshot["inventory_items"], kind="inventory")
        self._sync_inventory_buttons(snapshot["inventory_items"])
        self._show_item_feedback(str(snapshot.get("item_feedback_icon") or ""))
        self._maybe_auto_speak_snapshot(snapshot)

    def _maybe_auto_speak_snapshot(self, snapshot: dict[str, object]) -> None:
        settings = self.controller.get_capability_settings().tts
        if not settings.enabled or not settings.auto_speak:
            return
        speech = self.snapshot_renderer.snapshot_tts_speech(snapshot)
        if not speech:
            return
        key = (str(snapshot.get("event_preview", "")), speech)
        if key == self._last_auto_tts_key:
            return
        self._last_auto_tts_key = key
        result = self.capability_runtime.speak_text(speech)
        self.voice_status_label.setText(result.message)

    def _render_current_frame(self) -> None:
        self.live2d_surface.hide()
        self.spirit_surface.hide()
        self.sprite_label.show()
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

    def _render_live2d_frame(self, frame: PresentationFrame) -> None:
        self.sprite_label.hide()
        self.spirit_surface.hide()
        self.live2d_surface.show()
        self.live2d_surface.load_frame(frame, self.controller.resources.asset_dir)
        if self.desktop_mode:
            self.clearMask()

    def _render_portrait_frame(self, frame: PresentationFrame) -> None:
        self.sprite_label.hide()
        self.live2d_surface.hide()
        self.spirit_surface.show()
        self.spirit_surface.load_frame(frame, self.controller.resources.asset_dir)
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


def _model_fetch_reason(exc: Exception) -> str:
    message = str(exc)
    for reason in (
        "missing_api_key",
        "timeout",
        "invalid_response_json",
        "invalid_response_shape",
        "empty_model_list",
        "invalid_response_encoding",
        "invalid_response_bytes",
        "invalid_response_size",
    ):
        if reason in message:
            return reason
    return "provider_error"


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
