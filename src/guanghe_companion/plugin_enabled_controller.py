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
from uuid import uuid4

from .companion_story_runtime import CompanionStoryRuntime
from .emotional_memory import make_memory_id
from .focus_companion import FocusCompanionSettings, WindowsForegroundActivityReader
from .memory_album_controller import MemoryAlbumController
from .plugin_api import ActionRequest
from .plugin_center_controller import PluginCenterController
from .plugin_story_bridge import PluginStoryBridge
from .plugin_subsystem import PluginSubsystem
from .ai_context_builder import build_ai_context_payload
from .character_performance_profile import load_character_performance_profile
from .companion_dialogue_policy import CompanionDialoguePolicy
from .legacy_memory_migration import (
    _is_relationship_memory,
    _kind_and_tags,
    _legacy_title,
    migrate_legacy_entries,
)
from .persona import build_persona_payload

try:  # available after the overlay is applied to the full repository
    from .controller import CompanionController as _BaseController
    _HAS_UPSTREAM_CONTROLLER = True
    from .actions import CompanionActionRequest
    from .relationship import RelationshipService, normalize_player_alias
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
        self._initialize_personal_context()

    def _initialize_personal_context(self) -> None:
        memory = self.story_runtime.memory
        if not memory.store.migration_done("long_term_v1"):
            migrate_legacy_entries(memory, (entry.to_dict() for entry in self.long_term_memory_service.entries),
                                   now=int(self.now))
            memory.store.mark_migration_done("long_term_v1")
        if not memory.store.migration_done("player_alias_v1"):
            alias = normalize_player_alias(getattr(self.state, "player_alias", ""))
            # The old state field has no lineage. Import once on an unrevoked
            # first migration; never reconstruct forgotten facts from a save.
            if alias and not memory.store.context_epoch and not memory.valid_profile(now=int(self.now)).player_alias:
                self._write_player_alias_memory(alias, source="legacy_player_alias")
            memory.store.mark_migration_done("player_alias_v1")
        profile = load_character_performance_profile(self.resources.asset_dir)
        self._persona_payload = build_persona_payload(self.character_pack, profile, pack_dir=self.resources.asset_dir)
        self.ai_expressor.dialogue_policy = CompanionDialoguePolicy(performance_profile=profile)
        self._memory_epoch_seen = memory.store.context_epoch
        self._perception_epoch = self._memory_epoch_seen
        self._tools_epoch = self._memory_epoch_seen
        # The callback also refreshes the existing UI snapshot without replaying
        # a response produced from the revoked facts.
        self.memory_album_controller.on_invalidated = self._on_memory_invalidated

    def _replace_ai_expressor(self, next_expressor) -> None:
        super()._replace_ai_expressor(next_expressor)
        resources = getattr(self, "resources", None)
        if resources is not None:
            self.ai_expressor.dialogue_policy = CompanionDialoguePolicy(
                performance_profile=load_character_performance_profile(resources.asset_dir))

    def _write_player_alias_memory(self, alias: str, *, source: str = "explicit_user_alias") -> None:
        memory = self.story_runtime.memory
        now = int(self.now)
        if alias and memory.valid_profile(now=now).player_alias == alias:
            return
        epoch = memory.store.context_epoch
        profile = memory.store.load_profile()
        source_ids = set(profile.evidence.get(f"player_alias:{profile.player_alias}", {}))
        source_ids.update(entry.memory_id for entry in memory.store.load_memories()
                          if not entry.deleted and entry.metadata.get("profile_field") == "player_alias")
        for memory_id in source_ids:
            memory.forget(memory_id, now=now, expected_epoch=epoch)
            epoch = memory.store.context_epoch
        evidence = ()
        if alias:
            # A fresh explicit edit is new evidence even if the user re-enters
            # a previously forgotten alias at the same logical timestamp.
            entry = memory.remember(kind="玩家希望被记住", title="用户确认的称呼",
                summary=f"用户希望被称呼为：{alias}", source=source, now=now,
                tags=("关于你", "称呼"), user_confirmed=True,
                source_ids=(f"player_alias_edit:{uuid4().hex}",),
                metadata={"profile_field": "player_alias"}, expected_epoch=epoch)
            evidence = (entry.memory_id,)
        memory.update_bond_profile(player_alias=alias, source_memory_ids=evidence,
                                   now=now, expected_epoch=epoch)

    def set_player_alias(self, alias: str, *, include_ai_expression: bool = False):
        if getattr(self, "story_runtime", None) is None:
            return super().set_player_alias(alias, include_ai_expression=include_ai_expression)
        normalized = normalize_player_alias(alias)
        self._write_player_alias_memory(normalized)
        self._on_memory_invalidated()
        # Preserve the existing UI/save field and response contract. Model
        # context reads the evidenced V2 field, not this presentation copy.
        return super().set_player_alias(normalized, include_ai_expression=include_ai_expression)

    def upsert_long_term_memory(self, *, key: str, category: str, summary: str,
                               source: str = "local_api") -> dict[str, object]:
        """Compatibility host write through V2; a retired key stays retired.

        An independent explicit user statement may create a new source through
        the memory album. Replaying this old keyed synchronization API may not.
        """
        if getattr(self, "story_runtime", None) is None:
            return super().upsert_long_term_memory(key=key, category=category, summary=summary, source=source)
        key = " ".join(key.split())[:80]
        category = " ".join(category.split())[:40]
        summary = " ".join(summary.split())[:240]
        source = " ".join(source.split())[:40] or "local_api"
        if not key or not summary or not _is_relationship_memory(key, category):
            raise ValueError("legacy memory key/category is not eligible for durable companion memory")
        if source.casefold() in {"model", "assistant", "llm", "llm_generated", "assistant_generated", "model_generated"}:
            raise ValueError("model output is not evidence of a user fact or completed event")
        memory = self.story_runtime.memory
        epoch = memory.store.context_epoch
        if memory.store.is_retired_origin(legacy_key=key):
            raise ValueError("retired legacy memory key cannot be replayed; use a new explicit user confirmation")
        existing = next((entry for entry in memory.store.load_memories()
                         if not entry.deleted and entry.metadata.get("legacy_key") == key), None)
        kind, tags = _kind_and_tags(key, category)
        tags = tuple(tag for tag in tags if tag != "用户确认")
        if existing is not None:
            memory.store.upsert_memory(replace(existing, kind=kind, title=_legacy_title(kind, summary),
                summary=summary, source=source, tags=tags, user_confirmed=False, updated_at=int(self.now),
                metadata={**existing.metadata, "legacy_category": category}), expected_epoch=epoch)
        else:
            result = memory.remember(kind=kind, title=_legacy_title(kind, summary), summary=summary,
                source=source, now=int(self.now), importance=0.78, tags=tags, user_confirmed=False,
                metadata={"legacy_key": key, "legacy_category": category},
                source_ids=(f"legacy_key:{make_memory_id(key)}",), expected_epoch=epoch)
            if result.deleted:
                raise ValueError("retired legacy memory source cannot be replayed")
        if epoch != memory.store.context_epoch:
            self._on_memory_invalidated()
        return self.get_snapshot()

    def _dialogue_context_epoch(self) -> int:
        story = getattr(self, "story_runtime", None)
        return story.memory.store.context_epoch if story is not None else 0

    def _on_memory_invalidated(self) -> None:
        self._invalidate_host_dialogue()
        self._memory_epoch_seen = self._dialogue_context_epoch()
        self._perception_summary = ""
        self._tool_results = []
        self._perception_epoch = -1
        self._tools_epoch = -1
        self.last_feedback = "记忆已更新，我们接着聊。"
        self.last_delta_text = "回忆册已更新"
        self.last_events = self._build_events(effect="ATTENTION", include_ai_expression=False)

    def set_perception_summary(self, summary: str) -> None:
        super().set_perception_summary(summary)
        self._perception_epoch = self._dialogue_context_epoch()

    def set_tool_results(self, results: list[dict[str, object]]) -> None:
        super().set_tool_results(results)
        self._tools_epoch = self._dialogue_context_epoch()

    def submit_dialogue_request(self, request, *, include_ai_expression: bool = False):
        self._require_dialogue_idle()
        # A narrow, explicit user command creates a reviewable proposal. Normal
        # chats, model replies and hypothetical scenes cannot silently write facts.
        pending = self.story_runtime.memory.propose_explicit_user_memory(request.normalized_text(), now=int(self.now))
        snapshot = super().submit_dialogue_request(request, include_ai_expression=include_ai_expression and pending is None)
        if pending is not None:
            self.last_feedback = "这件事先放进待确认了，你可以在回忆册里确认或放弃。"
            self.last_delta_text = "有一条记忆等待确认"
            self.last_events = self._build_events(effect="ATTENTION", include_ai_expression=False)
            return self.get_snapshot()
        return snapshot

    def _prepare_host_memory(self, request) -> bool:
        return self.story_runtime.memory.propose_explicit_user_memory(
            request.normalized_text(), now=int(self.now),
        ) is not None

    def _expression_context_is_current(self, request) -> bool:
        story = getattr(self, "story_runtime", None)
        if story is None:
            return True
        return (request.persona.get("character_id") == self.state.character_id
                and request.emotional_memory.get("context_epoch") == story.memory.store.context_epoch)


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
        self.story_runtime.memory.store.expire_memories(now=int(self.now))
        epoch = self._dialogue_context_epoch()
        if epoch != getattr(self, "_memory_epoch_seen", epoch):
            self._on_memory_invalidated()
        # Legacy chat archives have no source-level lineage. Fence the whole old
        # inference window at revocation while preserving the readable archive.
        current_history = [entry for entry in self.dialogue_history if entry.context_epoch == epoch]
        base["recent_dialogue"] = build_ai_context_payload(dialogue_history=current_history).get("recent_dialogue", [])
        base["long_term_memory"] = []
        base["memory_context_epoch"] = epoch
        if epoch:
            base["perception_summary"] = self._perception_summary if self._perception_epoch == epoch else ""
            base["tool_results"] = self._tool_results if self._tools_epoch == epoch else []
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
        context["persona"] = dict(getattr(self, "_persona_payload", {}))
        if epoch:
            # Existing providers have no revocation contract. A new provider may
            # opt in only by attesting this character and current context epoch.
            sections = context.get("plugin_context", {})
            context["plugin_context"] = {key: value for key, value in sections.items()
                if isinstance(value, Mapping) and value.get("context_epoch") == epoch
                and value.get("character_id") == self.state.character_id}
        return context

    def switch_character(self, character_id: str, **kwargs: object):
        if character_id == self.character_pack.character_id:
            return self.get_snapshot()
        include_ai = bool(kwargs.pop("include_ai_expression", False))
        snapshot = super().switch_character(character_id, include_ai_expression=False, **kwargs)  # type: ignore[misc]
        data_root = Path(getattr(self, "user_data_root", None) or user_data_dir())
        self._focus_settings_path = _focus_preferences_path(data_root, character_id)
        self.story_runtime = CompanionStoryRuntime.create(
            user_data_root=data_root,
            character_id=character_id,
            focus_settings=_load_focus_settings(self._focus_settings_path),
        )
        self.memory_album_controller = MemoryAlbumController(self.story_runtime)
        self.plugin_story_bridge = PluginStoryBridge(self.story_runtime, self.plugin_subsystem.runtime, character_id)
        self._initialize_personal_context()
        if include_ai:
            self.last_events = self._build_events(effect="SWITCH", include_ai_expression=True)
        return self.get_snapshot()

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
