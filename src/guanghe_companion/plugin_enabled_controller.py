from __future__ import annotations

"""Drop-in CompanionController subclass with memory/focus/plugin extensions.

The overlay switches one import in ``app.py``. Existing game settlement remains
owned by the upstream controller; plugin actions receive a read-only snapshot
and may only return typed presentation/events/memory proposals.
"""

from collections.abc import Mapping
from dataclasses import asdict, replace
import json
from pathlib import Path
import time
from typing import Any

from .companion_story_runtime import CompanionStoryRuntime
from .focus_companion import FocusCompanionSettings, WindowsForegroundActivityReader
from .memory_album_controller import MemoryAlbumController
from .plugin_api import ActionRequest
from .plugin_center_controller import PluginCenterController
from .plugin_story_bridge import PluginStoryBridge
from .plugin_subsystem import PluginSubsystem

try:  # available after the overlay is applied to the full repository
    from .controller import CompanionController as _BaseController
    _HAS_UPSTREAM_CONTROLLER = True
    from .actions import CompanionActionRequest
    from .relationship import RelationshipService
    from .runtime_paths import plugins_root, user_data_dir
except ImportError:  # pragma: no cover - keeps the portable overlay importable
    _HAS_UPSTREAM_CONTROLLER = False
    class _BaseController:  # type: ignore[no-redef]
        pass
    CompanionActionRequest = object  # type: ignore[assignment]
    RelationshipService = None  # type: ignore[assignment]
    def plugins_root() -> Path: return Path.cwd() / "plugins"
    def user_data_dir() -> Path: return Path.cwd() / "data"


class PluginEnabledCompanionController(_BaseController):
    def __init__(self, *args: object, **kwargs: object) -> None:
        if not _HAS_UPSTREAM_CONTROLLER:
            raise RuntimeError("PluginEnabledCompanionController requires the full E-Moti repository")
        super().__init__(*args, **kwargs)  # type: ignore[misc]
        character_id = str(getattr(getattr(self, "state", None), "character_id", "xingxi_pixel_pet"))
        data_root = Path(getattr(self, "user_data_root", None) or user_data_dir())
        self._focus_settings_path = _focus_preferences_path(data_root, character_id)
        self.story_runtime = CompanionStoryRuntime.create(
            user_data_root=data_root,
            character_id=character_id,
            focus_settings=_load_focus_settings(self._focus_settings_path),
        )
        self._focus_activity_reader = WindowsForegroundActivityReader()
        self.memory_album_controller = MemoryAlbumController(self.story_runtime)
        self.plugin_subsystem = PluginSubsystem(application_root=plugins_root().parent, user_data_root=data_root)
        self.plugin_boot_report = self.plugin_subsystem.start()
        self.plugin_story_bridge = PluginStoryBridge(
            story=self.story_runtime,
            plugins=self.plugin_subsystem.runtime,
            character_id=character_id,
        )
        self.plugin_center_controller = PluginCenterController(
            self.plugin_subsystem,
            character_id_provider=lambda: str(getattr(self.state, "character_id", character_id)),
            state_snapshot_provider=self._plugin_state_snapshot,
        )
        self.plugin_center = self.plugin_center_controller


    def bind_plugin_capabilities(
        self,
        *,
        tts_manager: object | None = None,
        asr_transcriber: object | None = None,
        screen_observer: object | None = None,
        web_search_service: object | None = None,
        expression_provider: object | None = None,
    ) -> None:
        from .plugin_provider_adapters import (
            ASRProviderAdapter, ExpressionProviderAdapter, ScreenSummaryProviderAdapter,
            TTSProviderAdapter, WebSearchProviderAdapter,
        )
        providers: dict[str, object] = {}
        if expression_provider is not None:
            callback = getattr(expression_provider, "generate", None) or expression_provider
            providers["expression"] = ExpressionProviderAdapter(callback)
        if tts_manager is not None:
            callback = getattr(tts_manager, "speak", None) or tts_manager
            providers["tts"] = TTSProviderAdapter(
                callback,
                settings_provider=lambda: self.get_capability_settings().tts,
            )
        if asr_transcriber is not None:
            callback = getattr(asr_transcriber, "transcribe", None) or getattr(asr_transcriber, "_transcribe", None)
            if callable(callback):
                providers["asr"] = ASRProviderAdapter(
                    callback,
                    settings_provider=lambda: self.get_capability_settings().asr,
                )
        if screen_observer is not None:
            callback = getattr(screen_observer, "observe", None) or screen_observer
            providers["screen_summary"] = ScreenSummaryProviderAdapter(
                callback,
                settings_provider=lambda: self.get_capability_settings().screen_observation,
            )
        if web_search_service is not None:
            callback = getattr(web_search_service, "search", None) or web_search_service
            providers["web_search"] = WebSearchProviderAdapter(
                callback,
                settings_provider=lambda: self.get_capability_settings().web_search,
            )
        self.plugin_subsystem.bind_host_capabilities(**providers)

    def generate_plugin_expression(self, prompt: str) -> object:
        client = getattr(self.ai_expressor, "llm_client", None)
        if not callable(client):
            raise RuntimeError("LLM expression provider is not configured")
        return client(str(prompt))

    def get_focus_companion_view_model(self) -> dict[str, object]:
        return self.story_runtime.focus.snapshot().to_public_dict()

    def set_focus_companion_enabled(self, enabled: bool) -> dict[str, object]:
        settings = replace(self.story_runtime.focus.settings, enabled=bool(enabled)).normalized()
        self.story_runtime.focus.update_settings(settings)
        _save_focus_settings(self._focus_settings_path, settings)
        return self.get_focus_companion_view_model()

    def poll_focus_companion(self, *, now: float | None = None) -> list[dict[str, object]]:
        coordinator = self.story_runtime.focus
        if not coordinator.settings.enabled:
            return []
        current = time.time() if now is None else float(now)
        sample = self._focus_activity_reader.sample(observed_at=current)
        events = coordinator.process_sample(
            sample,
            now=current,
            pet_stability=float(getattr(self.state, "stability", 80.0)),
            pet_mode=str(getattr(self.state, "mode", "Calm")),
        )
        return self._present_focus_events(events)

    def inject_demo_focus(self, focused_minutes: int = 52, *, now: float | None = None):
        result = self.story_runtime.focus.inject_demo_focus(
            focused_minutes=focused_minutes,
            now=now,
            pet_stability=float(getattr(self.state, "stability", 80.0)),
            pet_mode=str(getattr(self.state, "mode", "Calm")),
        )
        return self._present_focus_events(result)

    def confirm_focus_break(self, *, now: float | None = None, duration_seconds_override: int | None = None):
        event = self.story_runtime.focus.confirm_break(
            now=now,
            duration_seconds_override=duration_seconds_override,
        )
        return self._present_focus_events((event,))[0]

    def snooze_focus_break(self, *, now: float | None = None):
        return self._present_focus_events((self.story_runtime.focus.snooze(now=now),))[0]

    def mute_focus_break_today(self, *, now: float | None = None):
        return self._present_focus_events((self.story_runtime.focus.mute_today(now=now),))[0]

    def tick_focus_companion(self, *, now: float | None = None) -> list[dict[str, object]]:
        current = time.time() if now is None else float(now)
        events = self.story_runtime.focus.tick(now=current)
        for index, event in enumerate(events):
            self.story_runtime.record_focus_completion(
                event,
                now=max(0, int(current)),
                event_id=f"focus-complete:{int(current)}:{index}",
            )
        return self._present_focus_events(events)

    def advance_tick(self, *, include_ai_expression: bool = True):
        snapshot = super().advance_tick(include_ai_expression=include_ai_expression)  # type: ignore[misc]
        events = self.tick_focus_companion()
        if not events:
            events = self.poll_focus_companion()
        return self.get_snapshot() if events else snapshot

    def _present_focus_events(self, events: object) -> list[dict[str, object]]:
        rows = list(events or ())
        if rows:
            event = rows[-1]
            self.last_motion = str(getattr(event, "motion", "Default"))
            self.last_feedback = str(getattr(event, "speech", ""))
            self.last_delta_text = "探头时刻不会修改养成状态"
            self.last_allowed = True
            self.last_events = self._build_events(effect="ATTENTION", include_ai_expression=False)
        return [event.to_public_dict() for event in rows]

    def _build_actions(self):
        rows = list(super()._build_actions())  # type: ignore[misc]
        subsystem = getattr(self, "plugin_subsystem", None)
        if subsystem is None:
            return rows
        existing = {str(row.get("action_id", "")) for row in rows if isinstance(row, Mapping)}
        for definition in subsystem.runtime.list_actions():
            if definition.action_id in existing:
                continue
            rows.append(
                {
                    "action_id": definition.action_id,
                    "label": definition.label,
                    "motion": "Default",
                    "enabled": True,
                    "description": definition.description,
                    "source": "plugin",
                }
            )
        return rows

    def perform_action_request(self, request: object, *, include_ai_expression: bool = True):
        action_id = str(getattr(request, "action_id", ""))
        if self.plugin_subsystem.runtime.action_owner(action_id):
            return self._perform_plugin_action(action_id, include_ai_expression=include_ai_expression)
        snapshot = super().perform_action_request(request, include_ai_expression=include_ai_expression)  # type: ignore[misc]
        self._record_last_host_events()
        return snapshot

    def use_inventory_request(self, request: object, *, include_ai_expression: bool = True):
        snapshot = super().use_inventory_request(request, include_ai_expression=include_ai_expression)  # type: ignore[misc]
        self._record_last_host_events()
        return snapshot

    def _perform_plugin_action(self, action_id: str, *, include_ai_expression: bool) -> dict[str, object]:
        self.plugin_story_bridge.plugins = self.plugin_subsystem.runtime
        now = int(getattr(self, "now", 0)) + 5
        self.now = now
        safe = self.plugin_subsystem.execute_action(
            ActionRequest(
                action_id=action_id,
                character_id=str(getattr(self.state, "character_id", "")),
                now=now,
                state_snapshot=self._plugin_state_snapshot(),
            )
        )
        if not safe.ok or safe.value is None:
            self.last_motion = "SwitchDown"
            self.last_feedback = safe.message or "这个扩展暂时没有回应。"
            self.last_delta_text = "插件动作未修改养成状态"
            self.last_allowed = False
        else:
            result = safe.value
            processed = self.plugin_story_bridge._process_execution(result)  # typed result; host persists proposals
            self.last_motion = result.motion
            self.last_feedback = result.speech or "星汐完成了一次扩展互动。"
            self.last_delta_text = "插件动作只更新扩展数据与共同回忆"
            self.last_allowed = True
            self.last_events = self._build_events(effect="ATTENTION", include_ai_expression=include_ai_expression)
        persist = getattr(self, "_persist", None)
        if callable(persist):
            persist()
        return self.get_snapshot()

    def _expression_context(self) -> dict[str, object]:
        base = super()._expression_context()  # type: ignore[misc]
        bridge = getattr(self, "plugin_story_bridge", None)
        if bridge is None:
            return base
        bridge.plugins = self.plugin_subsystem.runtime
        query = str(getattr(self, "_current_player_message", ""))
        stage = "初识"
        if RelationshipService is not None:
            try:
                stage = RelationshipService(self.state).stage()
            except Exception:
                pass
        context, _bundle, _assembly = bridge.build_expression_context(
            base,
            query=query,
            now=int(getattr(self, "now", 0)),
            relationship_stage=stage,
            state_snapshot=self._plugin_state_snapshot(),
        )
        return context

    def switch_character(self, character_id: str, **kwargs: object):
        snapshot = super().switch_character(character_id, **kwargs)  # type: ignore[misc]
        data_root = Path(getattr(self, "user_data_root", None) or user_data_dir())
        self._focus_settings_path = _focus_preferences_path(data_root, character_id)
        self.story_runtime = CompanionStoryRuntime.create(
            user_data_root=data_root,
            character_id=character_id,
            focus_settings=_load_focus_settings(self._focus_settings_path),
        )
        self.memory_album_controller = MemoryAlbumController(self.story_runtime)
        self.plugin_story_bridge = PluginStoryBridge(self.story_runtime, self.plugin_subsystem.runtime, character_id)
        return snapshot

    def close(self) -> None:
        try:
            subsystem = getattr(self, "plugin_subsystem", None)
            if subsystem is not None:
                subsystem.shutdown()
        finally:
            super().close()  # type: ignore[misc]

    def _record_last_host_events(self) -> None:
        rows = list(getattr(self, "last_events", ()) or ())
        if rows:
            self.plugin_story_bridge.record_settled_events(rows, now=int(getattr(self, "now", 0)))

    def _plugin_state_snapshot(self) -> dict[str, object]:
        state = getattr(self, "state", None)
        keys = ("character_id", "character_name", "focus", "charge", "stability", "mood", "trust", "coins", "level", "exp", "mode")
        return {key: getattr(state, key, None) for key in keys}


def _focus_preferences_path(data_root: Path, character_id: str) -> Path:
    return data_root / "characters" / character_id / "focus_companion_preferences.json"


def _load_focus_settings(path: Path) -> FocusCompanionSettings:
    if not path.is_file():
        return FocusCompanionSettings()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, Mapping):
            return FocusCompanionSettings()
        allowed = {key: payload[key] for key in asdict(FocusCompanionSettings()) if key in payload}
        return FocusCompanionSettings(**allowed).normalized()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return FocusCompanionSettings()


def _save_focus_settings(path: Path, settings: FocusCompanionSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(asdict(settings.normalized()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
