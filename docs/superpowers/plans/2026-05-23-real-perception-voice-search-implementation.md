# Real Perception Voice Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in real screen observation, explicit web search, TTS playback, and push-to-talk ASR to the E-Moti demo without giving those capabilities write access to companion state or saves.

**Architecture:** Add a separate capability settings store, then wire four small services into the existing controller and Qt UI. Screen and search results enter the existing typed expression context as sanitized read-only context; ASR becomes normal player input; TTS consumes only already validated assistant speech from typed snapshots/events.

**Tech Stack:** Python 3.11, PySide6, Pillow ImageGrab, OpenAI-compatible HTTP endpoints, ddgs, pyttsx3, QtMultimedia, sounddevice, soundfile, pytest fake adapters.

---

## Non-Negotiable Boundaries

- Do not edit `AI不用看.md`.
- Do not commit `data/companion_save.json`.
- Do not copy Shinsekai or BANDORI-PET-REV source, prompts, audio, character design, or assets. Reuse only architecture ideas.
- Do not add mouse, keyboard, clipboard, window-control, plugin-download, or autonomous computer-control behavior.
- Do not let LLM, screen observation, web search, TTS, or ASR modify `CompanionState`, inventory, relationship, memories, goals, or save files.
- Do not bypass typed events or typed snapshots. TTS uses speech after event validation; ASR uses `DialogueRequest`; screen/search use `ExpressionContextChain`.
- Screenshot bytes must remain in memory unless the user runs a packaging or diagnostic command that already creates build artifacts.
- API keys must be stored only in local settings files and must be hidden from UI summaries, logs, and `to_public_dict()` output.

## File Structure

### New Runtime Modules

- `src/guanghe_companion/capability_settings.py`
  - Dataclasses and JSON store for screen, web search, TTS, and ASR settings.
  - Normalizes provider ids, numeric bounds, URLs, paths, and strings.
  - Provides redacted public dictionaries for UI/debug display.

- `src/guanghe_companion/screen_observation.py`
  - Screenshot capture adapter using `Pillow.ImageGrab.grab(all_screens=True)`.
  - Image resize and PNG data URL conversion.
  - OpenAI-compatible vision summarizer with injectable transport.
  - Returns a typed result object; never writes screenshots to disk.

- `src/guanghe_companion/web_search.py`
  - Explicit search service with `ddgs` adapter and fake adapter seam for tests.
  - Sanitizes title, summary, URL, timestamp into existing `tool_results` shape.
  - Returns unavailable results when dependency/network/provider fails.

- `src/guanghe_companion/voice_tts.py`
  - TTS manager with queue, stop, text cleanup, and provider factory.
  - `windows_sapi` provider through `pyttsx3`.
  - `http_qwen3tts` provider through HTTP audio bytes and QtMultimedia playback.

- `src/guanghe_companion/voice_asr.py`
  - Push-to-talk recorder and transcriber service.
  - `openai_compatible` `/audio/transcriptions` provider.
  - `vosk` provider with explicit model path check.

### Existing Modules To Modify

- `src/guanghe_companion/runtime_paths.py`
  - Add `capability_settings_path()` and `tts_cache_dir()`.

- `src/guanghe_companion/controller.py`
  - Load/save capability settings.
  - Keep recent `perception_summary` and `tool_results` in read-only expression context.
  - Expose controller methods used by UI without state mutation side effects.

- `src/guanghe_companion/app.py`
  - Add "感知与搜索" UI page.
  - Upgrade "语音" page from disabled shell to real controls.
  - Add microphone button near desktop dialogue input.
  - Wire manual observation, auto observation timer, explicit search, TTS test/stop/auto speak, ASR start/stop.

- `src/guanghe_companion/expression_context.py`
  - Reuse existing sanitizers.
  - Add no state-writing behavior.

- `pyproject.toml`
  - Add demo runtime dependencies after they are covered by dependency-missing tests.

- `docs/demo_delivery.md`
  - Update only the demo feature notes and privacy notes after implementation.

### Tests To Add Or Modify

- Add `tests/test_capability_settings.py`
- Add `tests/test_screen_observation.py`
- Add `tests/test_web_search.py`
- Add `tests/test_voice_tts.py`
- Add `tests/test_voice_asr.py`
- Modify `tests/test_runtime_paths.py`
- Modify `tests/test_expression_context.py`
- Modify `tests/test_controller.py`
- Modify `tests/test_app.py`
- Modify `tests/test_desktop_pet_smoke.py`

---

## Task 1: Capability Settings Store

**Files:**
- Create: `src/guanghe_companion/capability_settings.py`
- Modify: `src/guanghe_companion/runtime_paths.py`
- Test: `tests/test_capability_settings.py`
- Test: `tests/test_runtime_paths.py`

- [ ] **Step 1: Write failing tests for defaults, redaction, normalization, and BOM JSON**

Create `tests/test_capability_settings.py`:

```python
from __future__ import annotations

import json

from guanghe_companion.capability_settings import (
    ASRSettings,
    CapabilitySettings,
    CapabilitySettingsStore,
    ScreenObservationSettings,
    TTSSettings,
    WebSearchSettings,
)


def test_default_capabilities_are_disabled() -> None:
    settings = CapabilitySettings.default()

    assert settings.screen_observation.enabled is False
    assert settings.screen_observation.auto_enabled is False
    assert settings.web_search.enabled is False
    assert settings.tts.enabled is False
    assert settings.asr.enabled is False


def test_store_round_trips_bom_json_and_redacts_secrets(tmp_path) -> None:
    path = tmp_path / "capability_settings.json"
    path.write_text(
        "\ufeff"
        + json.dumps(
            {
                "screen_observation": {
                    "enabled": True,
                    "auto_enabled": True,
                    "interval_seconds": 1,
                    "max_screenshot_width": 9999,
                    "vision_base_url": " https://vision.example.test/v1/ ",
                    "vision_api_key": "vision-secret",
                },
                "web_search": {"enabled": True, "max_results": 99},
                "tts": {"enabled": True, "provider": "Windows SAPI", "volume": 2.5},
                "asr": {"enabled": True, "provider": "OPENAI", "api_key": "asr-secret"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    settings = CapabilitySettingsStore(path).load()

    assert settings.screen_observation.interval_seconds == 10
    assert settings.screen_observation.max_screenshot_width == 1920
    assert settings.screen_observation.vision_base_url == "https://vision.example.test/v1/"
    assert settings.web_search.max_results == 5
    assert settings.tts.provider == "windows_sapi"
    assert settings.tts.volume == 1.0
    assert settings.asr.provider == "openai_compatible"

    public = settings.to_public_dict()
    assert public["screen_observation"]["vision_api_key"] == "***"
    assert public["asr"]["api_key"] == "***"
    assert "vision-secret" not in repr(public)
    assert "asr-secret" not in repr(public)


def test_store_save_creates_parent_and_writes_normalized_json(tmp_path) -> None:
    path = tmp_path / "nested" / "capability_settings.json"
    store = CapabilitySettingsStore(path)
    settings = CapabilitySettings(
        screen_observation=ScreenObservationSettings(enabled=True, interval_seconds=3),
        web_search=WebSearchSettings(enabled=True, max_results=0),
        tts=TTSSettings(enabled=True, provider="http-qwen3tts", volume=-1),
        asr=ASRSettings(enabled=True, max_record_seconds=99),
    )

    saved = store.save(settings)
    reloaded = store.load()

    assert saved.screen_observation.interval_seconds == 10
    assert reloaded.web_search.max_results == 1
    assert reloaded.tts.provider == "http_qwen3tts"
    assert reloaded.tts.volume == 0.0
    assert reloaded.asr.max_record_seconds == 30
```

Modify `tests/test_runtime_paths.py`:

```python
def test_capability_paths_use_user_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("E_MOTI_USER_DATA_DIR", str(tmp_path))

    from guanghe_companion.runtime_paths import capability_settings_path, tts_cache_dir

    assert capability_settings_path() == tmp_path / "capability_settings.json"
    assert tts_cache_dir() == tmp_path / "cache" / "tts"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests\test_capability_settings.py tests\test_runtime_paths.py -q
```

Expected failure:

```text
ModuleNotFoundError: No module named 'guanghe_companion.capability_settings'
```

- [ ] **Step 3: Implement capability settings**

Create `src/guanghe_companion/capability_settings.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _clean_string(value: object, *, max_length: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = "".join(" " if ord(ch) < 32 or ord(ch) == 127 else ch for ch in value.strip())
    return cleaned[:max_length]


def _bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _int(value: object, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(minimum, min(maximum, int(value)))
    return default


def _float(value: object, default: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(minimum, min(maximum, float(value)))
    return default


def _provider(value: object, default: str, aliases: dict[str, str]) -> str:
    raw = _clean_string(value, max_length=80).lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return default
    return aliases.get(raw, raw)


@dataclass(frozen=True, slots=True)
class ScreenObservationSettings:
    enabled: bool = False
    auto_enabled: bool = False
    interval_seconds: int = 60
    max_screenshot_width: int = 1280
    send_screenshot_to_vision: bool = True
    vision_provider: str = "openai_compatible"
    vision_model: str = ""
    vision_base_url: str = ""
    vision_api_key: str = ""
    timeout_seconds: int = 30

    @classmethod
    def from_dict(cls, data: object) -> "ScreenObservationSettings":
        source = data if isinstance(data, dict) else {}
        return cls(
            enabled=_bool(source.get("enabled")),
            auto_enabled=_bool(source.get("auto_enabled")),
            interval_seconds=_int(source.get("interval_seconds"), 60, 10, 600),
            max_screenshot_width=_int(source.get("max_screenshot_width"), 1280, 640, 1920),
            send_screenshot_to_vision=_bool(source.get("send_screenshot_to_vision"), True),
            vision_provider=_provider(
                source.get("vision_provider"),
                "openai_compatible",
                {"openai": "openai_compatible", "openai_compatible": "openai_compatible"},
            ),
            vision_model=_clean_string(source.get("vision_model"), max_length=120),
            vision_base_url=_clean_string(source.get("vision_base_url"), max_length=240),
            vision_api_key=_clean_string(source.get("vision_api_key"), max_length=400),
            timeout_seconds=_int(source.get("timeout_seconds"), 30, 5, 120),
        )


@dataclass(frozen=True, slots=True)
class WebSearchSettings:
    enabled: bool = False
    engine: str = "duckduckgo"
    max_results: int = 3
    timeout_seconds: int = 10
    show_sources: bool = True

    @classmethod
    def from_dict(cls, data: object) -> "WebSearchSettings":
        source = data if isinstance(data, dict) else {}
        return cls(
            enabled=_bool(source.get("enabled")),
            engine=_provider(source.get("engine"), "duckduckgo", {"ddg": "duckduckgo"}),
            max_results=_int(source.get("max_results"), 3, 1, 5),
            timeout_seconds=_int(source.get("timeout_seconds"), 10, 3, 60),
            show_sources=_bool(source.get("show_sources"), True),
        )


@dataclass(frozen=True, slots=True)
class TTSSettings:
    enabled: bool = False
    provider: str = "windows_sapi"
    api_url: str = "http://127.0.0.1:9880/"
    language: str = "zh"
    voice: str = ""
    rate: int = 0
    volume: float = 1.0
    auto_speak: bool = False

    @classmethod
    def from_dict(cls, data: object) -> "TTSSettings":
        source = data if isinstance(data, dict) else {}
        return cls(
            enabled=_bool(source.get("enabled")),
            provider=_provider(
                source.get("provider"),
                "windows_sapi",
                {"windows_sapi": "windows_sapi", "sapi": "windows_sapi", "http_qwen3tts": "http_qwen3tts"},
            ),
            api_url=_clean_string(source.get("api_url"), max_length=240) or "http://127.0.0.1:9880/",
            language=_clean_string(source.get("language"), max_length=16) or "zh",
            voice=_clean_string(source.get("voice"), max_length=120),
            rate=_int(source.get("rate"), 0, -10, 10),
            volume=_float(source.get("volume"), 1.0, 0.0, 1.0),
            auto_speak=_bool(source.get("auto_speak")),
        )


@dataclass(frozen=True, slots=True)
class ASRSettings:
    enabled: bool = False
    provider: str = "openai_compatible"
    model: str = "whisper-1"
    base_url: str = ""
    api_key: str = ""
    language: str = "zh"
    vosk_model_path: str = ""
    auto_send: bool = False
    max_record_seconds: int = 12

    @classmethod
    def from_dict(cls, data: object) -> "ASRSettings":
        source = data if isinstance(data, dict) else {}
        return cls(
            enabled=_bool(source.get("enabled")),
            provider=_provider(
                source.get("provider"),
                "openai_compatible",
                {"openai": "openai_compatible", "whisper": "openai_compatible", "vosk": "vosk"},
            ),
            model=_clean_string(source.get("model"), max_length=120) or "whisper-1",
            base_url=_clean_string(source.get("base_url"), max_length=240),
            api_key=_clean_string(source.get("api_key"), max_length=400),
            language=_clean_string(source.get("language"), max_length=16) or "zh",
            vosk_model_path=_clean_string(source.get("vosk_model_path"), max_length=500),
            auto_send=_bool(source.get("auto_send")),
            max_record_seconds=_int(source.get("max_record_seconds"), 12, 1, 30),
        )


@dataclass(frozen=True, slots=True)
class CapabilitySettings:
    screen_observation: ScreenObservationSettings = field(default_factory=ScreenObservationSettings)
    web_search: WebSearchSettings = field(default_factory=WebSearchSettings)
    tts: TTSSettings = field(default_factory=TTSSettings)
    asr: ASRSettings = field(default_factory=ASRSettings)

    @classmethod
    def default(cls) -> "CapabilitySettings":
        return cls()

    @classmethod
    def from_dict(cls, data: object) -> "CapabilitySettings":
        source = data if isinstance(data, dict) else {}
        return cls(
            screen_observation=ScreenObservationSettings.from_dict(source.get("screen_observation")),
            web_search=WebSearchSettings.from_dict(source.get("web_search")),
            tts=TTSSettings.from_dict(source.get("tts")),
            asr=ASRSettings.from_dict(source.get("asr")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_public_dict(self) -> dict[str, Any]:
        public = self.to_dict()
        if public["screen_observation"].get("vision_api_key"):
            public["screen_observation"]["vision_api_key"] = "***"
        if public["asr"].get("api_key"):
            public["asr"]["api_key"] = "***"
        return public


class CapabilitySettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> CapabilitySettings:
        if not self.path.exists():
            return CapabilitySettings.default()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return CapabilitySettings.default()
        return CapabilitySettings.from_dict(raw)

    def save(self, settings: CapabilitySettings) -> CapabilitySettings:
        normalized = CapabilitySettings.from_dict(settings.to_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(normalized.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return normalized
```

Modify `src/guanghe_companion/runtime_paths.py`:

```python
def capability_settings_path() -> Path:
    return user_data_dir() / "capability_settings.json"


def tts_cache_dir() -> Path:
    return user_data_dir() / "cache" / "tts"
```

- [ ] **Step 4: Run targeted tests and full tests**

Run:

```powershell
python -m pytest tests\test_capability_settings.py tests\test_runtime_paths.py -q
python -m pytest -q
```

Expected:

```text
all selected tests pass
full suite passes
```

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git status --short --untracked-files=all
git add src\guanghe_companion\capability_settings.py src\guanghe_companion\runtime_paths.py tests\test_capability_settings.py tests\test_runtime_paths.py
git commit -m "feat: add capability settings store"
```

Confirm `data/companion_save.json` is not staged.

---

## Task 2: Controller Integration And UI Skeleton

**Files:**
- Modify: `src/guanghe_companion/controller.py`
- Modify: `src/guanghe_companion/app.py`
- Test: `tests/test_controller.py`
- Test: `tests/test_app.py`
- Test: `tests/test_desktop_pet_smoke.py`

- [ ] **Step 1: Write failing controller tests for settings persistence and state isolation**

Add to `tests/test_controller.py`:

```python
def test_capability_settings_round_trip_does_not_change_growth_state(tmp_path):
    from guanghe_companion.capability_settings import CapabilitySettings, WebSearchSettings
    from guanghe_companion.controller import CompanionController

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    before = controller.get_snapshot()["state"]

    updated = controller.update_capability_settings(
        CapabilitySettings(web_search=WebSearchSettings(enabled=True, max_results=5))
    )
    after = controller.get_snapshot()["state"]

    assert updated.web_search.enabled is True
    assert updated.web_search.max_results == 5
    assert after == before


def test_read_only_expression_context_can_be_updated_without_saving_growth_state(tmp_path):
    from guanghe_companion.controller import CompanionController

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    before = controller.get_snapshot()["state"]

    controller.set_perception_summary("  屏幕里有一个代码编辑器和测试结果。  ")
    controller.set_tool_results(
        [
            {"source": "web", "title": "文档", "summary": "检索到的来源"},
            {"source": "web", "title": "额外", "summary": "第二条来源"},
        ]
    )
    context = controller._expression_context()

    assert context["perception_summary"] == "屏幕里有一个代码编辑器和测试结果。"
    assert context["tool_results"][0]["title"] == "文档"
    assert controller.get_snapshot()["state"] == before
```

- [ ] **Step 2: Write failing UI tests for pages and default disabled controls**

Add to `tests/test_app.py`:

```python
def test_capability_pages_have_safe_defaults(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    nav_labels = [button.text() for button in window.navigation_buttons]
    assert "感知与搜索" in nav_labels
    assert "语音" in nav_labels

    assert window.screen_observation_enabled_check.isChecked() is False
    assert window.screen_observation_auto_check.isChecked() is False
    assert window.web_search_enabled_check.isChecked() is False
    assert window.tts_enabled_check.isChecked() is False
    assert window.asr_enabled_check.isChecked() is False
    assert "不会自动点击" in window.perception_privacy_label.text()

    window.close()
    app.processEvents()


def test_capability_ui_save_round_trips_to_controller(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    window.screen_observation_enabled_check.setChecked(True)
    window.web_search_enabled_check.setChecked(True)
    window.tts_enabled_check.setChecked(True)
    window.asr_enabled_check.setChecked(True)
    window.capability_save_button.click()
    app.processEvents()

    settings = window.controller.get_capability_settings()
    assert settings.screen_observation.enabled is True
    assert settings.web_search.enabled is True
    assert settings.tts.enabled is True
    assert settings.asr.enabled is True
    assert "已保存" in window.capability_feedback_label.text()

    window.close()
    app.processEvents()
```

Modify `tests/test_desktop_pet_smoke.py` to include the microphone button object:

```python
def test_desktop_pet_dialogue_microphone_button_exists(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    assert window.dialogue_asr_button.text() in {"🎙", "Mic"}
    assert window.dialogue_asr_button.isEnabled() is False

    window.close()
    app.processEvents()
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
python -m pytest tests\test_controller.py::test_capability_settings_round_trip_does_not_change_growth_state tests\test_controller.py::test_read_only_expression_context_can_be_updated_without_saving_growth_state -q
python -m pytest tests\test_app.py::test_capability_pages_have_safe_defaults tests\test_app.py::test_capability_ui_save_round_trips_to_controller tests\test_desktop_pet_smoke.py -q
```

Expected failure:

```text
AttributeError: 'CompanionController' object has no attribute 'update_capability_settings'
AttributeError: 'CompanionWindow' object has no attribute 'screen_observation_enabled_check'
```

- [ ] **Step 4: Implement controller settings and read-only context storage**

Modify `src/guanghe_companion/controller.py` imports:

```python
from .capability_settings import CapabilitySettings, CapabilitySettingsStore
from .runtime_paths import capability_settings_path
```

Extend `CompanionController.__init__` signature:

```python
        capability_settings_path: Path | None = None,
        capability_settings_store: CapabilitySettingsStore | None = None,
```

Add initialization after dialogue history initialization:

```python
        self.capability_settings_path = (
            Path(capability_settings_path)
            if capability_settings_path is not None
            else capability_settings_path_func()
        )
        self.capability_settings_store = capability_settings_store or CapabilitySettingsStore(
            self.capability_settings_path
        )
        self.capability_settings = self.capability_settings_store.load()
        self._perception_summary = ""
        self._tool_results: list[dict[str, object]] = []
```

Use an alias import to avoid naming conflict:

```python
from .runtime_paths import capability_settings_path as capability_settings_path_func
```

Add public methods:

```python
    def get_capability_settings(self) -> CapabilitySettings:
        return self.capability_settings

    def update_capability_settings(self, settings: CapabilitySettings) -> CapabilitySettings:
        self.capability_settings = self.capability_settings_store.save(settings)
        return self.capability_settings

    def set_perception_summary(self, summary: str) -> None:
        self._perception_summary = summary if isinstance(summary, str) else ""

    def set_tool_results(self, results: list[dict[str, object]]) -> None:
        self._tool_results = list(results) if isinstance(results, list) else []
```

Extend `_expression_context()` before returning:

```python
        runtime_context = ExpressionContextChain(
            [
                lambda: {"perception_summary": self._perception_summary},
                lambda: {"tool_results": self._tool_results},
            ]
        )()
        if runtime_context:
            merged.update(runtime_context)
        return merged
```

Use the existing local variable name in `_expression_context()`; if the method currently returns `external_context`, rename it to `merged` in that method only.

- [ ] **Step 5: Implement UI skeleton controls**

Modify `src/guanghe_companion/app.py`:

```python
for index, label in enumerate(("总览", "互动", "背包", "感知与搜索", "隐私", "LLM表达", "表达规则", "语音")):
    ...
```

Add page construction:

```python
self.perception_search_page = QWidget()
self.perception_search_layout = QVBoxLayout(self.perception_search_page)
self.perception_search_layout.addWidget(self._build_screen_observation_settings_card())
self.perception_search_layout.addWidget(self._build_web_search_settings_card())
self.perception_search_layout.addStretch(1)
self.content_stack.addWidget(self.perception_search_page)
```

Add controls in `_build_screen_observation_settings_card()`:

```python
self.screen_observation_enabled_check = QCheckBox("启用屏幕观察")
self.screen_observation_auto_check = QCheckBox("自动观察")
self.screen_observation_interval_input = QSpinBox()
self.screen_observation_interval_input.setRange(10, 600)
self.screen_observation_max_width_input = QSpinBox()
self.screen_observation_max_width_input.setRange(640, 1920)
self.screen_observation_base_url_input = QLineEdit()
self.screen_observation_model_input = QLineEdit()
self.screen_observation_api_key_input = QLineEdit()
self.screen_observation_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
self.screen_observation_run_button = QPushButton("观察一次")
self.screen_observation_status_label = QLabel("屏幕观察未启用")
```

Add controls in `_build_web_search_settings_card()`:

```python
self.web_search_enabled_check = QCheckBox("启用联网搜索")
self.web_search_query_input = QLineEdit()
self.web_search_query_input.setPlaceholderText("输入要搜索的内容")
self.web_search_run_button = QPushButton("搜索并提供给星汐")
self.web_search_results_label = QLabel("暂无搜索结果")
```

Add capability save feedback shared by the page:

```python
self.capability_save_button = QPushButton("保存能力设置")
self.capability_save_button.clicked.connect(self._save_capability_settings_from_ui)
self.capability_feedback_label = QLabel("")
```

Add voice page controls:

```python
self.tts_enabled_check = QCheckBox("启用 TTS")
self.tts_provider_combo = QComboBox()
self.tts_provider_combo.addItems(["windows_sapi", "http_qwen3tts"])
self.tts_api_url_input = QLineEdit()
self.tts_test_button = QPushButton("测试朗读")
self.tts_stop_button = QPushButton("停止朗读")
self.tts_auto_speak_check = QCheckBox("自动朗读星汐回应")
self.asr_enabled_check = QCheckBox("启用 ASR")
self.asr_provider_combo = QComboBox()
self.asr_provider_combo.addItems(["openai_compatible", "vosk"])
self.asr_base_url_input = QLineEdit()
self.asr_api_key_input = QLineEdit()
self.asr_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
self.asr_model_input = QLineEdit()
self.asr_start_button = QPushButton("开始录音")
self.asr_stop_button = QPushButton("停止并识别")
self.asr_auto_send_check = QCheckBox("识别后自动发送")
self.voice_status_label = QLabel("语音能力未启用")
```

Add microphone button next to dialogue input:

```python
self.dialogue_asr_button = QPushButton("🎙")
self.dialogue_asr_button.setObjectName("DialogueAsrButton")
self.dialogue_asr_button.setToolTip("按住或点击后使用 ASR 输入")
self.dialogue_asr_button.setEnabled(False)
dialogue_layout.addWidget(self.dialogue_asr_button)
```

Add `_load_capability_settings_into_ui()` and `_save_capability_settings_from_ui()` using `CapabilitySettings(...)` and controller methods from Task 1.

- [ ] **Step 6: Run targeted UI tests and full tests**

Run:

```powershell
python -m pytest tests\test_controller.py tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest -q
```

Expected:

```text
controller, app, smoke, and full suite pass
```

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git status --short --untracked-files=all
git add src\guanghe_companion\controller.py src\guanghe_companion\app.py tests\test_controller.py tests\test_app.py tests\test_desktop_pet_smoke.py
git commit -m "feat: add capability settings ui"
```

Confirm `data/companion_save.json` is not staged.

---

## Task 3: Screen Observation Service

**Files:**
- Create: `src/guanghe_companion/screen_observation.py`
- Modify: `src/guanghe_companion/app.py`
- Modify: `src/guanghe_companion/controller.py`
- Test: `tests/test_screen_observation.py`
- Test: `tests/test_app.py`
- Test: `tests/test_expression_context.py`

- [ ] **Step 1: Write failing service tests with fake capture and fake vision transport**

Create `tests/test_screen_observation.py`:

```python
from __future__ import annotations

import base64
import io

from PIL import Image

from guanghe_companion.capability_settings import ScreenObservationSettings


def make_image(width=2000, height=1000):
    return Image.new("RGB", (width, height), "#336699")


def test_screenshot_is_resized_to_data_url_without_disk_write(tmp_path):
    from guanghe_companion.screen_observation import PillowScreenCapture, screenshot_to_png_data_url

    capture = PillowScreenCapture(grab_func=lambda all_screens: make_image())
    image = capture.capture()
    data_url = screenshot_to_png_data_url(image, max_width=640)

    assert data_url.startswith("data:image/png;base64,")
    payload = base64.b64decode(data_url.split(",", 1)[1])
    decoded = Image.open(io.BytesIO(payload))
    assert decoded.width == 640
    assert decoded.height == 320
    assert list(tmp_path.iterdir()) == []


def test_observation_service_sends_image_to_vision_and_sanitizes_summary():
    from guanghe_companion.screen_observation import ScreenObservationService

    requests = []

    def fake_transport(payload, timeout):
        requests.append((payload, timeout))
        return {"choices": [{"message": {"content": "  看到 IDE 和测试输出。\n还有控制字符\t  "}}]}

    service = ScreenObservationService(
        capture=lambda: make_image(1200, 600),
        vision_transport=fake_transport,
    )
    result = service.observe(
        ScreenObservationSettings(
            enabled=True,
            vision_base_url="https://vision.example.test/v1",
            vision_api_key="secret",
            vision_model="vision-test",
            timeout_seconds=12,
        )
    )

    assert result.ok is True
    assert result.summary == "看到 IDE 和测试输出。 还有控制字符"
    assert requests[0][1] == 12
    content = requests[0][0]["messages"][0]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_observation_disabled_or_missing_config_returns_reason():
    from guanghe_companion.screen_observation import ScreenObservationService

    service = ScreenObservationService(capture=lambda: make_image(), vision_transport=lambda payload, timeout: {})

    disabled = service.observe(ScreenObservationSettings(enabled=False))
    missing = service.observe(ScreenObservationSettings(enabled=True, vision_model="", vision_base_url=""))

    assert disabled.ok is False
    assert "未启用" in disabled.message
    assert missing.ok is False
    assert "视觉模型" in missing.message
```

Add to `tests/test_expression_context.py`:

```python
def test_runtime_perception_summary_is_sanitized_in_expression_context(tmp_path):
    from guanghe_companion.controller import CompanionController

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    controller.set_perception_summary("A" * 400 + "\n")

    context = controller._expression_context()

    assert len(context["perception_summary"]) == 240
    assert "\n" not in context["perception_summary"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests\test_screen_observation.py tests\test_expression_context.py::test_runtime_perception_summary_is_sanitized_in_expression_context -q
```

Expected failure:

```text
ModuleNotFoundError: No module named 'guanghe_companion.screen_observation'
```

- [ ] **Step 3: Implement screen observation service**

Create `src/guanghe_companion/screen_observation.py`:

```python
from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from PIL import Image, ImageGrab

from .capability_settings import ScreenObservationSettings
from .expression_context import _sanitize_perception_summary


@dataclass(frozen=True, slots=True)
class ScreenObservationResult:
    ok: bool
    message: str
    summary: str = ""


class PillowScreenCapture:
    def __init__(self, grab_func: Callable[..., Image.Image] | None = None) -> None:
        self._grab_func = grab_func or ImageGrab.grab

    def capture(self) -> Image.Image:
        return self._grab_func(all_screens=True)


def screenshot_to_png_data_url(image: Image.Image, *, max_width: int) -> str:
    if image.width > max_width:
        ratio = max_width / image.width
        image = image.resize((max_width, max(1, int(image.height * ratio))))
    output = io.BytesIO()
    image.convert("RGB").save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def openai_vision_transport(payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    base_url = str(payload.pop("_base_url")).rstrip("/")
    api_key = str(payload.pop("_api_key"))
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class ScreenObservationService:
    def __init__(
        self,
        *,
        capture: Callable[[], Image.Image] | None = None,
        vision_transport: Callable[[dict[str, Any], int], dict[str, Any]] | None = None,
    ) -> None:
        self._capture = capture or PillowScreenCapture().capture
        self._vision_transport = vision_transport or openai_vision_transport

    def observe(self, settings: ScreenObservationSettings) -> ScreenObservationResult:
        if not settings.enabled:
            return ScreenObservationResult(False, "屏幕观察未启用")
        if not settings.vision_model or not settings.vision_base_url or not settings.vision_api_key:
            return ScreenObservationResult(False, "缺少视觉模型、base_url 或 api_key")
        try:
            image = self._capture()
            data_url = screenshot_to_png_data_url(image, max_width=settings.max_screenshot_width)
            payload = {
                "_base_url": settings.vision_base_url,
                "_api_key": settings.vision_api_key,
                "model": settings.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请用不超过80个中文字符描述这张桌面截图里与用户当前任务相关的可见信息。不要推断隐私内容。",
                            },
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 120,
            }
            response = self._vision_transport(payload, settings.timeout_seconds)
            summary = _extract_summary(response)
            if not summary:
                return ScreenObservationResult(False, "视觉模型未返回摘要")
            return ScreenObservationResult(True, "屏幕观察完成", summary)
        except (OSError, ValueError, KeyError, urllib.error.URLError, TimeoutError) as exc:
            return ScreenObservationResult(False, f"屏幕观察失败：{exc}")


def _extract_summary(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    return _sanitize_perception_summary(message.get("content"))
```

- [ ] **Step 4: Wire manual and auto observation into UI**

Modify `src/guanghe_companion/app.py` imports:

```python
from PySide6.QtCore import QTimer
from .screen_observation import ScreenObservationService
```

Add window fields after controller setup:

```python
self.screen_observation_service = ScreenObservationService()
self.screen_observation_timer = QTimer(self)
self.screen_observation_timer.timeout.connect(self._run_screen_observation)
```

Connect UI:

```python
self.screen_observation_run_button.clicked.connect(self._run_screen_observation)
self.screen_observation_auto_check.toggled.connect(self._update_screen_observation_timer)
```

Add methods:

```python
def _run_screen_observation(self) -> None:
    self._save_capability_settings_from_ui()
    result = self.screen_observation_service.observe(
        self.controller.get_capability_settings().screen_observation
    )
    self.screen_observation_status_label.setText(result.message)
    if result.summary:
        self.controller.set_perception_summary(result.summary)
        self.screen_observation_status_label.setText(f"{result.message}：{result.summary}")


def _update_screen_observation_timer(self) -> None:
    settings = self.controller.get_capability_settings().screen_observation
    if settings.enabled and settings.auto_enabled:
        self.screen_observation_timer.start(settings.interval_seconds * 1000)
    else:
        self.screen_observation_timer.stop()
```

Call `_update_screen_observation_timer()` after saving capability settings and when loading settings into UI.

- [ ] **Step 5: Run targeted tests, UI tests, and full tests**

Run:

```powershell
python -m pytest tests\test_screen_observation.py tests\test_expression_context.py -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest -q
```

Expected:

```text
screen observation, expression context, UI, smoke, and full suite pass
```

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git status --short --untracked-files=all
git add src\guanghe_companion\screen_observation.py src\guanghe_companion\app.py src\guanghe_companion\controller.py tests\test_screen_observation.py tests\test_expression_context.py tests\test_app.py
git commit -m "feat: add vision screen observation"
```

Confirm `data/companion_save.json` is not staged.

---

## Task 4: Explicit Web Search

**Files:**
- Create: `src/guanghe_companion/web_search.py`
- Modify: `src/guanghe_companion/app.py`
- Modify: `src/guanghe_companion/controller.py`
- Modify: `pyproject.toml`
- Test: `tests/test_web_search.py`
- Test: `tests/test_app.py`
- Test: `tests/test_controller.py`

- [ ] **Step 1: Write failing tests for fake search, unavailable dependency, and state isolation**

Create `tests/test_web_search.py`:

```python
from __future__ import annotations

from guanghe_companion.capability_settings import WebSearchSettings


def test_fake_web_search_results_are_sanitized():
    from guanghe_companion.web_search import WebSearchService

    def fake_adapter(query, max_results, timeout):
        assert query == "星汐 demo"
        assert max_results == 2
        assert timeout == 9
        return [
            {
                "title": "  标题\n一  ",
                "body": "摘要\t内容" * 40,
                "href": "https://example.test/a",
            },
            {"title": "标题二", "body": "摘要二", "href": "https://example.test/b"},
        ]

    service = WebSearchService(adapter=fake_adapter)
    result = service.search("  星汐 demo  ", WebSearchSettings(enabled=True, max_results=2, timeout_seconds=9))

    assert result.ok is True
    assert len(result.tool_results) == 2
    assert result.tool_results[0]["source"] == "web_search"
    assert result.tool_results[0]["title"] == "标题 一"
    assert len(result.tool_results[0]["summary"]) <= 180
    assert result.tool_results[0]["url"] == "https://example.test/a"


def test_web_search_disabled_and_dependency_missing_are_explicit():
    from guanghe_companion.web_search import WebSearchService

    disabled = WebSearchService(adapter=lambda query, max_results, timeout: []).search(
        "query", WebSearchSettings(enabled=False)
    )
    missing = WebSearchService(adapter=None).search("query", WebSearchSettings(enabled=True))

    assert disabled.ok is False
    assert "未启用" in disabled.message
    assert missing.ok is False
    assert "ddgs" in missing.message
```

Add to `tests/test_controller.py`:

```python
def test_web_search_results_do_not_change_state(tmp_path):
    from guanghe_companion.controller import CompanionController

    controller = CompanionController(save_path=tmp_path / "save.json", auto_load=False)
    before = controller.get_snapshot()["state"]

    controller.set_tool_results(
        [{"source": "web_search", "title": "A", "summary": "B", "timestamp": "2026-05-23"}]
    )

    assert controller.get_snapshot()["state"] == before
    assert controller._expression_context()["tool_results"][0]["source"] == "web_search"
```

Add to `tests/test_app.py`:

```python
def test_search_shortcut_updates_tool_results_without_dialogue_submit(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    class FakeSearchService:
        def search(self, query, settings):
            from guanghe_companion.web_search import WebSearchResult

            return WebSearchResult(
                ok=True,
                message="搜索完成",
                tool_results=[{"source": "web_search", "title": query, "summary": "摘要"}],
            )

    window.web_search_service = FakeSearchService()
    window.web_search_enabled_check.setChecked(True)
    window.capability_save_button.click()
    window.dialogue_input.setText("/search 星汐")
    window._handle_dialogue_submit()

    assert window.dialogue_input.text() == ""
    assert window.controller._expression_context()["tool_results"][0]["title"] == "星汐"
    assert "搜索完成" in window.web_search_results_label.text()

    window.close()
    app.processEvents()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests\test_web_search.py tests\test_controller.py::test_web_search_results_do_not_change_state tests\test_app.py::test_search_shortcut_updates_tool_results_without_dialogue_submit -q
```

Expected failure:

```text
ModuleNotFoundError: No module named 'guanghe_companion.web_search'
```

- [ ] **Step 3: Implement web search service**

Create `src/guanghe_companion/web_search.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from .capability_settings import WebSearchSettings
from .expression_context import _sanitize_context_string


SearchAdapter = Callable[[str, int, int], Iterable[dict[str, object]]]


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    ok: bool
    message: str
    tool_results: list[dict[str, str]]


class WebSearchService:
    def __init__(self, adapter: SearchAdapter | None = None) -> None:
        self._adapter = adapter

    def search(self, query: str, settings: WebSearchSettings) -> WebSearchResult:
        if not settings.enabled:
            return WebSearchResult(False, "联网搜索未启用", [])
        query = _sanitize_context_string(query, 80)
        if not query:
            return WebSearchResult(False, "搜索词为空", [])
        adapter = self._adapter or _ddgs_adapter()
        if adapter is None:
            return WebSearchResult(False, "ddgs 未安装，无法执行联网搜索", [])
        try:
            raw_results = adapter(query, settings.max_results, settings.timeout_seconds)
        except Exception as exc:
            return WebSearchResult(False, f"联网搜索失败：{exc}", [])
        sanitized = _sanitize_search_results(raw_results, settings.max_results)
        if not sanitized:
            return WebSearchResult(False, "联网搜索没有返回可用来源", [])
        return WebSearchResult(True, "搜索完成，结果已提供给星汐", sanitized)


def _ddgs_adapter() -> SearchAdapter | None:
    try:
        from ddgs import DDGS
    except ImportError:
        return None

    def run(query: str, max_results: int, timeout: int) -> Iterable[dict[str, object]]:
        with DDGS(timeout=timeout) as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    return run


def _sanitize_search_results(raw_results: Iterable[dict[str, object]], max_results: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for entry in raw_results:
        if not isinstance(entry, dict):
            continue
        title = _sanitize_context_string(str(entry.get("title") or ""), 80)
        summary = _sanitize_context_string(str(entry.get("body") or entry.get("summary") or ""), 180)
        url = _sanitize_context_string(str(entry.get("href") or entry.get("url") or ""), 240)
        if not title or not summary:
            continue
        item = {
            "source": "web_search",
            "title": title,
            "summary": summary,
            "timestamp": timestamp,
        }
        if url:
            item["url"] = url
        results.append(item)
        if len(results) >= max_results:
            break
    return results
```

- [ ] **Step 4: Wire search button and `/search` shortcut**

Modify `src/guanghe_companion/app.py` imports:

```python
from .web_search import WebSearchService
```

Add window field:

```python
self.web_search_service = WebSearchService()
```

Connect search button:

```python
self.web_search_run_button.clicked.connect(self._run_web_search_from_ui)
```

Add methods:

```python
def _run_web_search_from_ui(self) -> None:
    query = self.web_search_query_input.text()
    self._run_web_search(query)


def _run_web_search(self, query: str) -> None:
    self._save_capability_settings_from_ui()
    result = self.web_search_service.search(query, self.controller.get_capability_settings().web_search)
    self.web_search_results_label.setText(result.message)
    if result.tool_results:
        self.controller.set_tool_results(result.tool_results)
        lines = [result.message]
        for item in result.tool_results:
            lines.append(f"{item.get('title', '')}｜{item.get('summary', '')}")
        self.web_search_results_label.setText("\n".join(lines))
```

Modify `_handle_dialogue_submit()`:

```python
text = self.dialogue_input.text().strip()
if text.startswith("/search "):
    query = text[len("/search ") :].strip()
    self.dialogue_input.clear()
    self._run_web_search(query)
    return
request = DialogueRequest(text=text)
```

Modify `pyproject.toml`:

```toml
dependencies = ["PySide6==6.11.0", "Pillow>=12.1.0", "ddgs>=9.0.0"]
```

- [ ] **Step 5: Run search tests, UI tests, and full tests**

Run:

```powershell
python -m pytest tests\test_web_search.py tests\test_controller.py::test_web_search_results_do_not_change_state -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest -q
```

Expected:

```text
web search, UI, smoke, and full suite pass
```

- [ ] **Step 6: Commit Task 4**

Run:

```powershell
git status --short --untracked-files=all
git add src\guanghe_companion\web_search.py src\guanghe_companion\app.py src\guanghe_companion\controller.py pyproject.toml tests\test_web_search.py tests\test_controller.py tests\test_app.py
git commit -m "feat: add explicit web search context"
```

Confirm `data/companion_save.json` is not staged.

---

## Task 5: TTS Playback

**Files:**
- Create: `src/guanghe_companion/voice_tts.py`
- Modify: `src/guanghe_companion/app.py`
- Modify: `pyproject.toml`
- Test: `tests/test_voice_tts.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write failing tests for text cleanup, queue, stop, and fake HTTP payload**

Create `tests/test_voice_tts.py`:

```python
from __future__ import annotations

from guanghe_companion.capability_settings import TTSSettings


def test_clean_tts_text_removes_action_tags_and_sources():
    from guanghe_companion.voice_tts import clean_tts_text

    text = clean_tts_text("[smile]你好。```json\n{\"source\":\"web\"}\n```<动作>")

    assert text == "你好。"


def test_tts_manager_queues_and_stops_with_fake_provider():
    from guanghe_companion.voice_tts import TTSManager, TTSResult

    spoken = []

    class FakeProvider:
        def speak(self, text, settings):
            spoken.append((text, settings.provider))
            return TTSResult(True, "done")

        def stop(self):
            spoken.append(("stop", settings.provider))

    settings = TTSSettings(enabled=True, provider="windows_sapi")
    manager = TTSManager(provider_factory=lambda provider: FakeProvider())

    assert manager.speak("第一句", settings).ok is True
    assert manager.speak("第二句", settings).ok is True
    manager.stop(settings)

    assert spoken[0] == ("第一句", "windows_sapi")
    assert spoken[1] == ("第二句", "windows_sapi")
    assert spoken[2] == ("stop", "windows_sapi")


def test_http_tts_provider_sends_expected_payload(tmp_path):
    from guanghe_companion.voice_tts import HttpQwen3TTSProvider

    requests = []

    def fake_post(url, payload, timeout):
        requests.append((url, payload, timeout))
        return b"RIFF....WAVEfmt "

    provider = HttpQwen3TTSProvider(post=fake_post, cache_dir=tmp_path)
    result = provider.speak(
        "测试文本",
        TTSSettings(
            enabled=True,
            provider="http_qwen3tts",
            api_url="http://127.0.0.1:9880/",
            language="zh",
            voice="xingxi",
        ),
    )

    assert result.ok is True
    assert requests[0][0] == "http://127.0.0.1:9880/"
    assert requests[0][1]["text"] == "测试文本"
    assert requests[0][1]["voice"] == "xingxi"
    assert any(path.suffix == ".wav" for path in tmp_path.iterdir())
```

Add to `tests/test_app.py`:

```python
def test_auto_tts_consumes_snapshot_speech_after_validation(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    spoken = []

    class FakeTTS:
        def speak(self, text, settings):
            spoken.append(text)
            from guanghe_companion.voice_tts import TTSResult

            return TTSResult(True, "ok")

    window.tts_manager = FakeTTS()
    window.tts_enabled_check.setChecked(True)
    window.tts_auto_speak_check.setChecked(True)
    window.capability_save_button.click()

    snapshot = window.controller.get_snapshot()
    snapshot["speech"] = "星汐的 typed speech"
    window._apply_snapshot(snapshot)

    assert spoken == ["星汐的 typed speech"]

    window.close()
    app.processEvents()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests\test_voice_tts.py tests\test_app.py::test_auto_tts_consumes_snapshot_speech_after_validation -q
```

Expected failure:

```text
ModuleNotFoundError: No module named 'guanghe_companion.voice_tts'
```

- [ ] **Step 3: Implement TTS manager and providers**

Create `src/guanghe_companion/voice_tts.py`:

```python
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .capability_settings import TTSSettings
from .runtime_paths import tts_cache_dir


@dataclass(frozen=True, slots=True)
class TTSResult:
    ok: bool
    message: str


def clean_tts_text(text: str) -> str:
    cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"\[[^\]]{1,40}\]", "", cleaned)
    cleaned = re.sub(r"<[^>]{1,40}>", "", cleaned)
    return " ".join(cleaned.split())


class TTSManager:
    def __init__(self, provider_factory: Callable[[str], object] | None = None) -> None:
        self._provider_factory = provider_factory or create_tts_provider

    def speak(self, text: str, settings: TTSSettings) -> TTSResult:
        if not settings.enabled:
            return TTSResult(False, "TTS 未启用")
        cleaned = clean_tts_text(text)
        if not cleaned:
            return TTSResult(False, "没有可朗读文本")
        provider = self._provider_factory(settings.provider)
        if provider is None:
            return TTSResult(False, f"TTS provider 不可用：{settings.provider}")
        return provider.speak(cleaned, settings)

    def stop(self, settings: TTSSettings) -> None:
        provider = self._provider_factory(settings.provider)
        if provider is not None and hasattr(provider, "stop"):
            provider.stop()


class WindowsSapiTTSProvider:
    def __init__(self) -> None:
        self._engine = None

    def _load_engine(self):
        if self._engine is None:
            import pyttsx3

            self._engine = pyttsx3.init()
        return self._engine

    def speak(self, text: str, settings: TTSSettings) -> TTSResult:
        try:
            engine = self._load_engine()
            if settings.rate:
                engine.setProperty("rate", int(engine.getProperty("rate")) + settings.rate * 10)
            engine.setProperty("volume", settings.volume)
            if settings.voice:
                engine.setProperty("voice", settings.voice)
            engine.say(text)
            engine.runAndWait()
            return TTSResult(True, "朗读完成")
        except Exception as exc:
            return TTSResult(False, f"Windows SAPI TTS 失败：{exc}")

    def stop(self) -> None:
        if self._engine is not None:
            self._engine.stop()


class HttpQwen3TTSProvider:
    def __init__(
        self,
        *,
        post: Callable[[str, dict[str, object], int], bytes] | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self._post = post or _post_audio
        self._cache_dir = cache_dir or tts_cache_dir()

    def speak(self, text: str, settings: TTSSettings) -> TTSResult:
        try:
            payload = {"text": text, "language": settings.language, "voice": settings.voice}
            audio = self._post(settings.api_url, payload, 30)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            suffix = ".wav" if audio.startswith(b"RIFF") else ".mp3"
            output = self._cache_dir / f"{uuid4().hex}{suffix}"
            output.write_bytes(audio)
            return TTSResult(True, f"已生成朗读音频：{output.name}")
        except Exception as exc:
            return TTSResult(False, f"HTTP TTS 失败：{exc}")

    def stop(self) -> None:
        return None


def _post_audio(url: str, payload: dict[str, object], timeout: int) -> bytes:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def create_tts_provider(provider: str):
    if provider == "windows_sapi":
        return WindowsSapiTTSProvider()
    if provider == "http_qwen3tts":
        return HttpQwen3TTSProvider()
    return None
```

- [ ] **Step 4: Wire TTS UI controls and auto speak**

Modify `src/guanghe_companion/app.py` imports:

```python
from .voice_tts import TTSManager
```

Add window field:

```python
self.tts_manager = TTSManager()
self._last_auto_spoken_text = ""
```

Connect controls:

```python
self.tts_test_button.clicked.connect(self._test_tts)
self.tts_stop_button.clicked.connect(self._stop_tts)
```

Add methods:

```python
def _test_tts(self) -> None:
    self._save_capability_settings_from_ui()
    result = self.tts_manager.speak("星汐在这里，语音测试正常。", self.controller.get_capability_settings().tts)
    self.voice_status_label.setText(result.message)


def _stop_tts(self) -> None:
    self.tts_manager.stop(self.controller.get_capability_settings().tts)
    self.voice_status_label.setText("已停止朗读")
```

In `_apply_snapshot()` after speech label update:

```python
speech = str(snapshot.get("speech") or "")
tts_settings = self.controller.get_capability_settings().tts
if tts_settings.enabled and tts_settings.auto_speak and speech and speech != self._last_auto_spoken_text:
    self._last_auto_spoken_text = speech
    result = self.tts_manager.speak(speech, tts_settings)
    self.voice_status_label.setText(result.message)
```

Modify `pyproject.toml`:

```toml
dependencies = ["PySide6==6.11.0", "Pillow>=12.1.0", "ddgs>=9.0.0", "pyttsx3>=2.99"]
```

- [ ] **Step 5: Run TTS tests, UI tests, and full tests**

Run:

```powershell
python -m pytest tests\test_voice_tts.py -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest -q
```

Expected:

```text
TTS, UI, smoke, and full suite pass
```

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git status --short --untracked-files=all
git add src\guanghe_companion\voice_tts.py src\guanghe_companion\app.py pyproject.toml tests\test_voice_tts.py tests\test_app.py
git commit -m "feat: add tts playback providers"
```

Confirm `data/companion_save.json` is not staged.

---

## Task 6: Push-To-Talk ASR

**Files:**
- Create: `src/guanghe_companion/voice_asr.py`
- Modify: `src/guanghe_companion/app.py`
- Modify: `pyproject.toml`
- Test: `tests/test_voice_asr.py`
- Test: `tests/test_app.py`
- Test: `tests/test_controller.py`

- [ ] **Step 1: Write failing tests for fake recorder, OpenAI-compatible request, Vosk missing model, and UI fill**

Create `tests/test_voice_asr.py`:

```python
from __future__ import annotations

from guanghe_companion.capability_settings import ASRSettings


def test_fake_recorder_and_transcriber_return_text():
    from guanghe_companion.voice_asr import ASRService, ASRResult

    service = ASRService(
        recorder=lambda seconds: b"wav-bytes",
        transcriber=lambda audio, settings: ASRResult(True, "识别完成", "你好星汐"),
    )

    result = service.record_and_transcribe(ASRSettings(enabled=True, max_record_seconds=3))

    assert result.ok is True
    assert result.text == "你好星汐"


def test_openai_asr_transcriber_sends_auth_without_leaking_key():
    from guanghe_companion.voice_asr import OpenAICompatibleASRTranscriber

    requests = []

    def fake_post(url, headers, data, timeout):
        requests.append((url, headers, data, timeout))
        return {"text": "测试语音"}

    transcriber = OpenAICompatibleASRTranscriber(post=fake_post)
    result = transcriber.transcribe(
        b"wav",
        ASRSettings(
            enabled=True,
            provider="openai_compatible",
            base_url="https://asr.example.test/v1",
            api_key="secret-key",
            model="whisper-1",
            language="zh",
        ),
    )

    assert result.ok is True
    assert result.text == "测试语音"
    assert requests[0][0] == "https://asr.example.test/v1/audio/transcriptions"
    assert requests[0][1]["Authorization"] == "Bearer secret-key"
    assert "secret-key" not in result.message


def test_vosk_missing_model_returns_explicit_error(tmp_path):
    from guanghe_companion.voice_asr import VoskASRTranscriber

    result = VoskASRTranscriber().transcribe(
        b"wav",
        ASRSettings(enabled=True, provider="vosk", vosk_model_path=str(tmp_path / "missing")),
    )

    assert result.ok is False
    assert "模型路径不存在" in result.message
```

Add to `tests/test_app.py`:

```python
def test_asr_button_fills_dialogue_input(monkeypatch, tmp_path):
    app, window = make_window(monkeypatch, tmp_path)

    class FakeASR:
        def record_and_transcribe(self, settings):
            from guanghe_companion.voice_asr import ASRResult

            return ASRResult(True, "识别完成", "你好星汐")

    window.asr_service = FakeASR()
    window.asr_enabled_check.setChecked(True)
    window.capability_save_button.click()
    window._run_asr_once()

    assert window.dialogue_input.text() == "你好星汐"
    assert "识别完成" in window.voice_status_label.text()

    window.close()
    app.processEvents()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests\test_voice_asr.py tests\test_app.py::test_asr_button_fills_dialogue_input -q
```

Expected failure:

```text
ModuleNotFoundError: No module named 'guanghe_companion.voice_asr'
```

- [ ] **Step 3: Implement ASR service and providers**

Create `src/guanghe_companion/voice_asr.py`:

```python
from __future__ import annotations

import json
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable
from urllib import request

from .capability_settings import ASRSettings


@dataclass(frozen=True, slots=True)
class ASRResult:
    ok: bool
    message: str
    text: str = ""


class ASRService:
    def __init__(
        self,
        *,
        recorder: Callable[[int], bytes] | None = None,
        transcriber: Callable[[bytes, ASRSettings], ASRResult] | None = None,
    ) -> None:
        self._recorder = recorder or record_wav_bytes
        self._transcriber = transcriber

    def record_and_transcribe(self, settings: ASRSettings) -> ASRResult:
        if not settings.enabled:
            return ASRResult(False, "ASR 未启用")
        try:
            audio = self._recorder(settings.max_record_seconds)
        except Exception as exc:
            return ASRResult(False, f"录音失败：{exc}")
        transcriber = self._transcriber or create_asr_transcriber(settings.provider).transcribe
        return transcriber(audio, settings)


def record_wav_bytes(seconds: int) -> bytes:
    import sounddevice as sd

    samplerate = 16000
    channels = 1
    frames = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=channels, dtype="int16")
    sd.wait()
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(samplerate)
        wav.writeframes(frames.tobytes())
    return output.getvalue()


class OpenAICompatibleASRTranscriber:
    def __init__(self, post: Callable[[str, dict[str, str], bytes, int], dict[str, object]] | None = None) -> None:
        self._post = post or _post_multipart

    def transcribe(self, audio: bytes, settings: ASRSettings) -> ASRResult:
        if not settings.base_url or not settings.api_key:
            return ASRResult(False, "缺少 ASR base_url 或 api_key")
        try:
            url = f"{settings.base_url.rstrip('/')}/audio/transcriptions"
            headers = {"Authorization": f"Bearer {settings.api_key}"}
            payload = json.dumps(
                {"model": settings.model, "language": settings.language, "audio_base64": audio.hex()}
            ).encode("utf-8")
            response = self._post(url, headers, payload, 60)
            text = str(response.get("text") or "").strip()
            if not text:
                return ASRResult(False, "ASR 未返回文本")
            return ASRResult(True, "识别完成", text)
        except Exception as exc:
            return ASRResult(False, f"ASR 请求失败：{exc}")


class VoskASRTranscriber:
    def transcribe(self, audio: bytes, settings: ASRSettings) -> ASRResult:
        model_path = Path(settings.vosk_model_path)
        if not model_path.exists():
            return ASRResult(False, "Vosk 模型路径不存在")
        try:
            import vosk

            model = vosk.Model(str(model_path))
            recognizer = vosk.KaldiRecognizer(model, 16000)
            recognizer.AcceptWaveform(audio)
            data = json.loads(recognizer.FinalResult())
            text = str(data.get("text") or "").strip()
            return ASRResult(True, "识别完成", text) if text else ASRResult(False, "Vosk 未返回文本")
        except Exception as exc:
            return ASRResult(False, f"Vosk 识别失败：{exc}")


def create_asr_transcriber(provider: str):
    if provider == "vosk":
        return VoskASRTranscriber()
    return OpenAICompatibleASRTranscriber()


def _post_multipart(url: str, headers: dict[str, str], data: bytes, timeout: int) -> dict[str, object]:
    req = request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))
```

- [ ] **Step 4: Wire ASR UI**

Modify `src/guanghe_companion/app.py` imports:

```python
from .voice_asr import ASRService
```

Add window field:

```python
self.asr_service = ASRService()
```

Connect controls:

```python
self.asr_start_button.clicked.connect(self._run_asr_once)
self.asr_stop_button.clicked.connect(self._run_asr_once)
self.dialogue_asr_button.clicked.connect(self._run_asr_once)
```

Enable microphone button in `_load_capability_settings_into_ui()`:

```python
self.dialogue_asr_button.setEnabled(settings.asr.enabled)
```

Add method:

```python
def _run_asr_once(self) -> None:
    self._save_capability_settings_from_ui()
    settings = self.controller.get_capability_settings().asr
    result = self.asr_service.record_and_transcribe(settings)
    self.voice_status_label.setText(result.message)
    if result.text:
        self.dialogue_input.setText(result.text)
        if settings.auto_send:
            self._handle_dialogue_submit()
```

Modify `pyproject.toml`:

```toml
dependencies = [
    "PySide6==6.11.0",
    "Pillow>=12.1.0",
    "ddgs>=9.0.0",
    "pyttsx3>=2.99",
    "sounddevice>=0.4.6",
    "soundfile>=0.12.1",
]
```

Do not add `vosk` as a hard dependency in this task. The app must show a clear missing-provider message when Vosk is not installed.

- [ ] **Step 5: Run ASR tests, UI tests, and full tests**

Run:

```powershell
python -m pytest tests\test_voice_asr.py -q
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py -q
python -m pytest -q
```

Expected:

```text
ASR, UI, smoke, and full suite pass
```

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git status --short --untracked-files=all
git add src\guanghe_companion\voice_asr.py src\guanghe_companion\app.py pyproject.toml tests\test_voice_asr.py tests\test_app.py
git commit -m "feat: add asr dialogue input"
```

Confirm `data/companion_save.json` is not staged.

---

## Task 7: Packaging And Delivery Regression

**Files:**
- Modify: `docs/demo_delivery.md`
- Modify: packaging config files only if build commands reveal missing hidden imports or data files
- Test: `tests/test_app.py`
- Test: `tests/test_desktop_pet_smoke.py`

- [ ] **Step 1: Write a packaging regression checklist into delivery docs**

Modify only the feature and privacy sections of `docs/demo_delivery.md`:

```markdown
### Real Perception / Voice / Search Demo Checks

- Screen observation is opt-in. Manual observation sends a resized screenshot to the configured vision model and stores only the returned short summary in runtime memory.
- Automatic observation is opt-in and stops when the control panel closes.
- Web search is explicit through the search panel or `/search query`; results are shown as sources and passed to expression context as read-only tool results.
- TTS reads only Starry Xi speech that already came through typed events.
- ASR fills the player input box and optionally submits it as a normal dialogue request.
- None of these capabilities modify growth state, inventory, relationship, memories, goals, or save files.
```

- [ ] **Step 2: Run full test suite and JSON validation**

Run:

```powershell
python -m pytest -q
python -m json.tool assets\companion\original_oc\shop_items.json
```

Expected:

```text
full suite passes
shop_items.json prints formatted JSON and exits with code 0
```

- [ ] **Step 3: Build frozen app**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
```

Expected:

```text
dist\E-Moti\E-Moti.exe exists
```

Verify:

```powershell
if (!(Test-Path -LiteralPath 'dist\E-Moti\E-Moti.exe')) { throw 'dist\E-Moti\E-Moti.exe missing' }
```

- [ ] **Step 4: Run frozen control panel and pet-mode smoke**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$exe = (Resolve-Path 'dist\E-Moti\E-Moti.exe').Path
$p = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 5
if ($p.HasExited) { throw "control panel exited early" }
Stop-Process -Id $p.Id -Force
$p = Start-Process -FilePath $exe -ArgumentList '--pet-mode','--demo-save' -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 5
if ($p.HasExited) { throw "pet mode exited early" }
Stop-Process -Id $p.Id -Force
```

Expected:

```text
both processes stay alive for 5 seconds and are stopped by the smoke script
```

- [ ] **Step 5: Build installer and verify file exists**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
if (!(Test-Path -LiteralPath 'dist\installer\E-Moti_Setup_0.1.0.exe')) { throw 'installer missing' }
```

Expected:

```text
dist\installer\E-Moti_Setup_0.1.0.exe exists
```

- [ ] **Step 6: Inspect final git state**

Run:

```powershell
git status --short --untracked-files=all
git diff --name-only --cached
```

Expected:

```text
data/companion_save.json is not staged
build artifacts are not staged unless they were already tracked
```

- [ ] **Step 7: Commit Task 7**

Run:

```powershell
git add docs\demo_delivery.md
git status --short --untracked-files=all
git commit -m "docs: update delivery notes for perception voice search"
```

If packaging config files were changed to make the frozen build pass, include those specific files in the same commit.

---

## Final Verification Gate

- [ ] Run the required baseline commands:

```powershell
git status --short --untracked-files=all
git log --oneline --decorate -10
git remote -v
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
```

- [ ] Run UI-specific tests:

```powershell
python -m pytest tests\test_app.py tests\test_desktop_pet_smoke.py
```

- [ ] Run packaging if dependencies or frozen import behavior changed:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1 -SkipAppBuild
```

- [ ] Manually QA the foreground visuals:

```text
1. Open the control panel.
2. Confirm "感知与搜索" and "语音" pages are visible and not visually crowded.
3. Confirm API keys are password fields.
4. Confirm disabled capabilities show plain disabled status instead of scary errors.
5. Confirm desktop pet dialogue input, send button, and microphone button fit at desktop and narrow widths.
6. Confirm privacy copy says screenshots are opt-in, not stored long term, and no automatic click/input/clipboard control exists.
```

- [ ] Manual LLM integration QA with user's configured keys:

```text
1. Use model list retrieval in existing LLM expression settings.
2. Use "测试 LLM 回应" and confirm timeout settings are honored.
3. Enable screen observation with the same compatible provider only if that provider supports image input.
4. Run manual observation once and verify summary appears.
5. Run explicit search once and verify sources appear.
6. Enable TTS and verify one provider can speak or returns a clear provider error.
7. Enable ASR and verify missing microphone/provider produces a clear status message.
```

- [ ] Confirm no forbidden files are staged:

```powershell
git diff --cached --name-only | Select-String -Pattern 'AI不用看.md|data/companion_save.json' -SimpleMatch
```

Expected:

```text
no output
```

---

## Commit Sequence

1. `feat: add capability settings store`
2. `feat: add capability settings ui`
3. `feat: add vision screen observation`
4. `feat: add explicit web search context`
5. `feat: add tts playback providers`
6. `feat: add asr dialogue input`
7. `docs: update delivery notes for perception voice search`

This sequence gives a working checkpoint after each capability and keeps rollback small if a provider or dependency creates packaging trouble.
