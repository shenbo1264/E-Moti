from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .capability_settings import CapabilitySettings
from .voice_provider_catalog import asr_provider_ids, tts_provider_ids


class CapabilitySettingsPanel(QWidget):
    saveRequested = Signal()
    screenObservationRequested = Signal()
    webSearchRequested = Signal(str)

    def __init__(self, settings: CapabilitySettings | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.perception_search_layout = QVBoxLayout(self)
        self.perception_search_layout.setContentsMargins(0, 0, 0, 0)
        self.perception_search_layout.setSpacing(12)

        self.screen_observation_settings_card = self._build_screen_observation_settings_card()
        self.web_search_settings_card = self._build_web_search_settings_card()
        self.proactive_companion_settings_card = self._build_proactive_companion_settings_card()
        self.perception_search_layout.addWidget(self.screen_observation_settings_card)
        self.perception_search_layout.addWidget(self.web_search_settings_card)
        self.perception_search_layout.addWidget(self.proactive_companion_settings_card)

        capability_save_row = QHBoxLayout()
        self.capability_save_button = QPushButton("保存能力设置")
        self.capability_save_button.clicked.connect(self.saveRequested)
        self.capability_feedback_label = QLabel("")
        self.capability_feedback_label.setWordWrap(True)
        capability_save_row.addWidget(self.capability_save_button)
        capability_save_row.addWidget(self.capability_feedback_label, stretch=1)
        self.perception_search_layout.addLayout(capability_save_row)
        self.perception_search_layout.addStretch(1)
        self.load_settings(settings or CapabilitySettings.default())

    def load_settings(self, settings: CapabilitySettings) -> None:
        screen = settings.screen_observation
        self.screen_observation_enabled_check.setChecked(screen.enabled)
        self.screen_observation_auto_check.setChecked(screen.auto_enabled)
        self.screen_observation_interval_input.setValue(screen.interval_seconds)
        self.screen_observation_max_width_input.setValue(screen.max_screenshot_width)
        self.screen_observation_model_input.setText(screen.vision_model)
        self.screen_observation_base_url_input.setText(screen.vision_base_url)
        self.screen_observation_api_key_input.setText(screen.vision_api_key)

        search = settings.web_search
        self.web_search_enabled_check.setChecked(search.enabled)
        _set_combo_current_text(self.web_search_engine_combo, search.engine)
        self.web_search_max_results_input.setValue(search.max_results)

        proactive = settings.proactive_companion
        self.proactive_companion_enabled_check.setChecked(proactive.enabled)
        self.proactive_interval_input.setValue(proactive.interval_seconds)
        self.proactive_global_cooldown_input.setValue(proactive.global_cooldown_seconds)
        self.proactive_daily_limit_input.setValue(proactive.daily_limit)
        self.proactive_quiet_hours_check.setChecked(proactive.quiet_hours_enabled)
        self.proactive_quiet_start_input.setText(proactive.quiet_start)
        self.proactive_quiet_end_input.setText(proactive.quiet_end)
        self.proactive_allow_context_topic_check.setChecked(proactive.allow_context_topic)

    def collect_settings(self, base: CapabilitySettings | None = None) -> CapabilitySettings:
        source = base or CapabilitySettings.default()
        screen = replace(
            source.screen_observation,
            enabled=self.screen_observation_enabled_check.isChecked(),
            auto_enabled=self.screen_observation_auto_check.isChecked(),
            interval_seconds=self.screen_observation_interval_input.value(),
            max_screenshot_width=self.screen_observation_max_width_input.value(),
            vision_model=self.screen_observation_model_input.text(),
            vision_base_url=self.screen_observation_base_url_input.text(),
            vision_api_key=self.screen_observation_api_key_input.text(),
        )
        search = replace(
            source.web_search,
            enabled=self.web_search_enabled_check.isChecked(),
            engine=self.web_search_engine_combo.currentText(),
            max_results=self.web_search_max_results_input.value(),
        )
        proactive = replace(
            source.proactive_companion,
            enabled=self.proactive_companion_enabled_check.isChecked(),
            interval_seconds=self.proactive_interval_input.value(),
            global_cooldown_seconds=self.proactive_global_cooldown_input.value(),
            daily_limit=self.proactive_daily_limit_input.value(),
            quiet_hours_enabled=self.proactive_quiet_hours_check.isChecked(),
            quiet_start=self.proactive_quiet_start_input.text(),
            quiet_end=self.proactive_quiet_end_input.text(),
            allow_context_topic=self.proactive_allow_context_topic_check.isChecked(),
        )
        return replace(
            source,
            screen_observation=screen,
            web_search=search,
            proactive_companion=proactive,
        )

    def set_feedback(self, text: str) -> None:
        self.capability_feedback_label.setText(text)

    def set_screen_status(self, text: str) -> None:
        self.screen_observation_status_label.setText(text)

    def set_search_results(self, text: str) -> None:
        self.web_search_results_label.setText(text)

    def _build_screen_observation_settings_card(self) -> QGroupBox:
        box = QGroupBox("屏幕观察")
        layout = QGridLayout(box)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        self.screen_observation_enabled_check = QCheckBox("启用屏幕观察")
        self.screen_observation_auto_check = QCheckBox("自动观察")
        self.screen_observation_interval_input = QSpinBox()
        self.screen_observation_interval_input.setRange(10, 600)
        self.screen_observation_max_width_input = QSpinBox()
        self.screen_observation_max_width_input.setRange(640, 1920)
        self.screen_observation_model_input = QLineEdit()
        self.screen_observation_model_input.setPlaceholderText("视觉模型 ID")
        self.screen_observation_base_url_input = QLineEdit()
        self.screen_observation_base_url_input.setPlaceholderText("OpenAI-compatible Base URL")
        self.screen_observation_api_key_input = QLineEdit()
        self.screen_observation_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.screen_observation_api_key_input.setPlaceholderText("视觉 API Key")
        self.screen_observation_run_button = QPushButton("观察一次")
        self.screen_observation_run_button.clicked.connect(self.screenObservationRequested)
        self.screen_observation_status_label = QLabel("屏幕观察未运行")
        self.screen_observation_status_label.setWordWrap(True)

        layout.addWidget(self.screen_observation_enabled_check, 0, 0)
        layout.addWidget(self.screen_observation_auto_check, 0, 1)
        layout.addWidget(QLabel("间隔秒数"), 1, 0)
        layout.addWidget(self.screen_observation_interval_input, 1, 1)
        layout.addWidget(QLabel("最长边"), 1, 2)
        layout.addWidget(self.screen_observation_max_width_input, 1, 3)
        layout.addWidget(QLabel("模型"), 2, 0)
        layout.addWidget(self.screen_observation_model_input, 2, 1, 1, 3)
        layout.addWidget(QLabel("Base URL"), 3, 0)
        layout.addWidget(self.screen_observation_base_url_input, 3, 1, 1, 3)
        layout.addWidget(QLabel("API Key"), 4, 0)
        layout.addWidget(self.screen_observation_api_key_input, 4, 1, 1, 3)
        layout.addWidget(self.screen_observation_run_button, 5, 0)
        layout.addWidget(self.screen_observation_status_label, 5, 1, 1, 3)
        return box

    def _build_web_search_settings_card(self) -> QGroupBox:
        box = QGroupBox("联网搜索")
        layout = QGridLayout(box)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        self.web_search_enabled_check = QCheckBox("启用联网搜索")
        self.web_search_engine_combo = QComboBox()
        self.web_search_engine_combo.addItems(["duckduckgo"])
        self.web_search_max_results_input = QSpinBox()
        self.web_search_max_results_input.setRange(1, 5)
        self.web_search_query_input = QLineEdit()
        self.web_search_query_input.setPlaceholderText("输入要搜索的内容")
        self.web_search_run_button = QPushButton("搜索并提供给星汐")
        self.web_search_run_button.clicked.connect(lambda: self.webSearchRequested.emit(self.web_search_query_input.text()))
        self.web_search_results_label = QLabel("暂无搜索结果")
        self.web_search_results_label.setWordWrap(True)

        layout.addWidget(self.web_search_enabled_check, 0, 0)
        layout.addWidget(QLabel("引擎"), 1, 0)
        layout.addWidget(self.web_search_engine_combo, 1, 1)
        layout.addWidget(QLabel("结果数"), 1, 2)
        layout.addWidget(self.web_search_max_results_input, 1, 3)
        layout.addWidget(self.web_search_query_input, 2, 0, 1, 3)
        layout.addWidget(self.web_search_run_button, 2, 3)
        layout.addWidget(self.web_search_results_label, 3, 0, 1, 4)
        return box

    def _build_proactive_companion_settings_card(self) -> QGroupBox:
        box = QGroupBox("主动陪伴")
        layout = QGridLayout(box)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        self.proactive_companion_enabled_check = QCheckBox("启用低频主动陪伴")
        self.proactive_interval_input = QSpinBox()
        self.proactive_interval_input.setRange(60, 86_400)
        self.proactive_global_cooldown_input = QSpinBox()
        self.proactive_global_cooldown_input.setRange(60, 86_400)
        self.proactive_daily_limit_input = QSpinBox()
        self.proactive_daily_limit_input.setRange(1, 24)
        self.proactive_quiet_hours_check = QCheckBox("启用安静时段")
        self.proactive_quiet_start_input = QLineEdit()
        self.proactive_quiet_start_input.setPlaceholderText("23:00")
        self.proactive_quiet_end_input = QLineEdit()
        self.proactive_quiet_end_input.setPlaceholderText("08:00")
        self.proactive_allow_context_topic_check = QCheckBox("允许基于只读上下文轻提醒")

        layout.addWidget(self.proactive_companion_enabled_check, 0, 0, 1, 2)
        layout.addWidget(self.proactive_allow_context_topic_check, 0, 2, 1, 2)
        layout.addWidget(QLabel("最小间隔秒数"), 1, 0)
        layout.addWidget(self.proactive_interval_input, 1, 1)
        layout.addWidget(QLabel("全局冷却秒数"), 1, 2)
        layout.addWidget(self.proactive_global_cooldown_input, 1, 3)
        layout.addWidget(QLabel("每日上限"), 2, 0)
        layout.addWidget(self.proactive_daily_limit_input, 2, 1)
        layout.addWidget(self.proactive_quiet_hours_check, 2, 2, 1, 2)
        layout.addWidget(QLabel("安静开始"), 3, 0)
        layout.addWidget(self.proactive_quiet_start_input, 3, 1)
        layout.addWidget(QLabel("安静结束"), 3, 2)
        layout.addWidget(self.proactive_quiet_end_input, 3, 3)
        return box


class ManualPerceptionPanel(QGroupBox):
    manualPerceptionRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("屏幕感知", parent)
        layout = QVBoxLayout(self)
        self.perception_status_label = QLabel("屏幕感知：关闭")
        self.perception_status_label.setWordWrap(True)
        self.perception_privacy_label = QLabel("默认不会读取屏幕；只在手动触发时显示隐私提示。本轮不会自动截图，不会自动点击、输入或操作电脑。")
        self.perception_privacy_label.setWordWrap(True)
        self.observe_screen_button = QPushButton("手动触发屏幕感知")
        self.observe_screen_button.setMinimumHeight(36)
        self.observe_screen_button.clicked.connect(self.manualPerceptionRequested)
        layout.addWidget(self.perception_status_label)
        layout.addWidget(self.perception_privacy_label)
        layout.addWidget(self.observe_screen_button)

    def set_status(self, text: str) -> None:
        self.perception_status_label.setText(text)


class VoiceSettingsPanel(QGroupBox):
    ttsTestRequested = Signal()
    ttsStopRequested = Signal()
    asrStartRequested = Signal()
    asrStopRequested = Signal()
    voiceServicePreflightRequested = Signal()
    voiceServiceLaunchRequested = Signal()

    def __init__(
        self,
        settings: CapabilitySettings | None = None,
        expression_settings: Mapping[str, object] | None = None,
        character_voice_profile: Mapping[str, object] | QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        if isinstance(character_voice_profile, QWidget) and parent is None:
            parent = character_voice_profile
            character_voice_profile = None
        super().__init__("语音", parent)
        layout = QGridLayout(self)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        self.voice_status_label = QLabel("TTS 暂未启用 / ASR 暂未启用")
        self.voice_status_label.setWordWrap(True)
        self.voice_tts_provider_label = QLabel("tts_provider: disabled")
        self.voice_asr_provider_label = QLabel("asr_provider: disabled")
        self.voice_character_profile_label = QLabel("")
        self.voice_character_profile_label.setWordWrap(True)
        self.voice_service_status_label = QLabel("语音服务：未检查，优先使用 exe 随包脚本。")
        self.voice_service_status_label.setWordWrap(True)
        self.voice_service_preflight_button = QPushButton("检查语音服务")
        self.voice_service_preflight_button.clicked.connect(self.voiceServicePreflightRequested)
        self.voice_service_launch_button = QPushButton("启动随包语音服务")
        self.voice_service_launch_button.clicked.connect(self.voiceServiceLaunchRequested)

        self.tts_enabled_check = QCheckBox("启用 TTS")
        self.tts_provider_combo = QComboBox()
        self.tts_provider_combo.addItems(list(tts_provider_ids()))
        self.tts_api_url_input = QLineEdit()
        self.tts_api_url_input.setPlaceholderText("http://127.0.0.1:9880/")
        self.tts_model_variant_combo = QComboBox()
        self.tts_model_variant_combo.addItems(
            ["qwen3tts_0.6b_customvoice", "qwen3tts_1.7b_customvoice", "gptsovits_v2"]
        )
        self.tts_auto_speak_check = QCheckBox("自动朗读星汐回复")
        self.tts_test_button = QPushButton("测试朗读")
        self.tts_test_button.clicked.connect(self.ttsTestRequested)
        self.tts_stop_button = QPushButton("停止朗读")
        self.tts_stop_button.clicked.connect(self.ttsStopRequested)
        self.tts_enabled_check.toggled.connect(self.sync_controls_enabled)

        self.asr_enabled_check = QCheckBox("启用 ASR")
        self.asr_provider_combo = QComboBox()
        self.asr_provider_combo.addItems(list(asr_provider_ids()))
        self.asr_model_input = QLineEdit()
        self.asr_model_input.setPlaceholderText("whisper-1")
        self.asr_base_url_input = QLineEdit()
        self.asr_base_url_input.setPlaceholderText("OpenAI-compatible Base URL")
        self.asr_api_key_input = QLineEdit()
        self.asr_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.asr_api_key_input.setPlaceholderText("ASR API Key")
        self.asr_auto_send_check = QCheckBox("识别后自动发送")
        self.asr_hotkey_enabled_check = QCheckBox("启用 ASR 快捷键")
        self.asr_hotkey_input = QLineEdit()
        self.asr_hotkey_input.setPlaceholderText("Ctrl+Alt+M")
        self.asr_start_button = QPushButton("开始录音")
        self.asr_start_button.clicked.connect(self.asrStartRequested)
        self.asr_stop_button = QPushButton("停止并识别")
        self.asr_stop_button.clicked.connect(self.asrStopRequested)
        self.asr_enabled_check.toggled.connect(self.sync_controls_enabled)
        self.asr_hotkey_enabled_check.toggled.connect(self.sync_controls_enabled)

        self.voice_tts_enable_button = QPushButton("启用 TTS")
        self.voice_tts_enable_button.setEnabled(False)
        self.voice_asr_enable_button = QPushButton("启用 ASR")
        self.voice_asr_enable_button.setEnabled(False)

        layout.addWidget(self.voice_status_label, 0, 0, 1, 4)
        layout.addWidget(self.voice_tts_provider_label, 1, 0, 1, 2)
        layout.addWidget(self.voice_asr_provider_label, 1, 2, 1, 2)
        layout.addWidget(self.voice_character_profile_label, 2, 0, 1, 4)
        layout.addWidget(self.tts_enabled_check, 3, 0)
        layout.addWidget(QLabel("TTS provider"), 4, 0)
        layout.addWidget(self.tts_provider_combo, 4, 1)
        layout.addWidget(QLabel("TTS API URL"), 5, 0)
        layout.addWidget(self.tts_api_url_input, 5, 1, 1, 3)
        layout.addWidget(QLabel("TTS model/profile"), 6, 0)
        layout.addWidget(self.tts_model_variant_combo, 6, 1)
        layout.addWidget(self.tts_auto_speak_check, 7, 0)
        layout.addWidget(self.tts_test_button, 7, 1)
        layout.addWidget(self.tts_stop_button, 7, 2)
        layout.addWidget(self.asr_enabled_check, 8, 0)
        layout.addWidget(QLabel("ASR provider"), 9, 0)
        layout.addWidget(self.asr_provider_combo, 9, 1)
        layout.addWidget(QLabel("ASR model"), 9, 2)
        layout.addWidget(self.asr_model_input, 9, 3)
        layout.addWidget(QLabel("ASR Base URL"), 10, 0)
        layout.addWidget(self.asr_base_url_input, 10, 1, 1, 3)
        layout.addWidget(QLabel("ASR API Key"), 11, 0)
        layout.addWidget(self.asr_api_key_input, 11, 1, 1, 3)
        layout.addWidget(self.asr_auto_send_check, 12, 0)
        layout.addWidget(self.asr_start_button, 12, 1)
        layout.addWidget(self.asr_stop_button, 12, 2)
        layout.addWidget(self.asr_hotkey_enabled_check, 13, 0)
        layout.addWidget(QLabel("ASR 快捷键"), 13, 1)
        layout.addWidget(self.asr_hotkey_input, 13, 2, 1, 2)
        layout.addWidget(self.voice_tts_enable_button, 14, 0)
        layout.addWidget(self.voice_asr_enable_button, 14, 1)
        layout.addWidget(self.voice_service_status_label, 15, 0, 1, 2)
        layout.addWidget(self.voice_service_preflight_button, 15, 2)
        layout.addWidget(self.voice_service_launch_button, 15, 3)
        self.load_settings(
            settings or CapabilitySettings.default(),
            expression_settings or {},
            character_voice_profile if isinstance(character_voice_profile, Mapping) else None,
        )

    def load_settings(
        self,
        settings: CapabilitySettings,
        expression_settings: Mapping[str, object],
        character_voice_profile: Mapping[str, object] | None = None,
    ) -> None:
        tts = settings.tts
        asr = settings.asr
        self.voice_tts_provider_label.setText(f"tts_provider: {expression_settings.get('tts_provider', 'disabled')}")
        self.voice_asr_provider_label.setText(f"asr_provider: {expression_settings.get('asr_provider', 'disabled')}")
        self.set_character_voice_profile(character_voice_profile or {})
        self.tts_enabled_check.setChecked(tts.enabled)
        _set_combo_current_text(self.tts_provider_combo, tts.provider)
        self.tts_api_url_input.setText(tts.api_url)
        _set_combo_current_text(self.tts_model_variant_combo, tts.model_variant)
        self.tts_auto_speak_check.setChecked(tts.auto_speak)
        self.asr_enabled_check.setChecked(asr.enabled)
        _set_combo_current_text(self.asr_provider_combo, asr.provider)
        self.asr_model_input.setText(asr.model)
        self.asr_base_url_input.setText(asr.base_url)
        self.asr_api_key_input.setText(asr.api_key)
        self.asr_auto_send_check.setChecked(asr.auto_send)
        self.asr_hotkey_enabled_check.setChecked(asr.hotkey_enabled)
        self.asr_hotkey_input.setText(asr.hotkey_sequence)
        self.sync_controls_enabled()

    def collect_settings(self, base: CapabilitySettings | None = None) -> CapabilitySettings:
        source = base or CapabilitySettings.default()
        tts = replace(
            source.tts,
            enabled=self.tts_enabled_check.isChecked(),
            provider=self.tts_provider_combo.currentText(),
            api_url=self.tts_api_url_input.text(),
            model_variant=self.tts_model_variant_combo.currentText(),
            auto_speak=self.tts_auto_speak_check.isChecked(),
        )
        asr = replace(
            source.asr,
            enabled=self.asr_enabled_check.isChecked(),
            provider=self.asr_provider_combo.currentText(),
            model=self.asr_model_input.text(),
            base_url=self.asr_base_url_input.text(),
            api_key=self.asr_api_key_input.text(),
            auto_send=self.asr_auto_send_check.isChecked(),
            hotkey_enabled=self.asr_hotkey_enabled_check.isChecked(),
            hotkey_sequence=self.asr_hotkey_input.text(),
        )
        return replace(source, tts=tts, asr=asr)

    def sync_controls_enabled(self) -> None:
        tts_enabled = self.tts_enabled_check.isChecked()
        self.tts_test_button.setEnabled(tts_enabled)
        self.tts_stop_button.setEnabled(tts_enabled)
        asr_enabled = self.asr_enabled_check.isChecked()
        self.asr_start_button.setEnabled(asr_enabled)
        self.asr_stop_button.setEnabled(asr_enabled)
        self.asr_hotkey_enabled_check.setEnabled(asr_enabled)
        self.asr_hotkey_input.setEnabled(asr_enabled and self.asr_hotkey_enabled_check.isChecked())

    def set_status(self, text: str) -> None:
        self.voice_status_label.setText(text)

    def set_service_status(self, text: str) -> None:
        self.voice_service_status_label.setText(text)

    def set_character_voice_profile(self, profile: Mapping[str, object]) -> None:
        self.voice_character_profile_label.setText(_voice_profile_summary(profile))


def _set_combo_current_text(combo: QComboBox, value: str) -> None:
    index = combo.findText(value)
    if index < 0 and value:
        combo.addItem(value)
        index = combo.findText(value)
    combo.setCurrentIndex(max(0, index))


def _voice_profile_summary(profile: Mapping[str, object]) -> str:
    if not profile:
        return "character_voice_profile: not defined"
    display = _profile_text(profile.get("display_name"))
    profile_id = _profile_text(profile.get("profile_id"))
    label = display or profile_id or "unnamed profile"
    details = [
        label,
        profile_id if profile_id and profile_id != label else "",
        _profile_detail("provider", profile.get("provider")),
        _profile_detail("voice", profile.get("voice")),
        _profile_detail("model", profile.get("model_variant")),
        _profile_detail("source", profile.get("voice_source_type")),
        _profile_detail("training", profile.get("training_status")),
    ]
    return "character_voice_profile: " + " | ".join(item for item in details if item)


def _profile_detail(label: str, value: object) -> str:
    text = _profile_text(value)
    return f"{label}: {text}" if text else ""


def _profile_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value.strip())[:120].strip()
