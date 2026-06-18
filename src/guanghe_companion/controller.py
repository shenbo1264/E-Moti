from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from .actions import CompanionActionLayer, CompanionActionRequest, action_label
from .ai_expressor import (
    ShinsekaiAIExpressor,
    build_default_ai_expressor,
)
from .capability_settings import CapabilitySettings, CapabilitySettingsStore
from .character_pack import DEFAULT_CHARACTER_ID, resolve_motion_caption
from .character_resources import CharacterResources, load_character_resources, load_character_resources_from_dir
from .character_session import build_character_session_paths
from .dialogue import DialogueRequest
from .dialogue_history import (
    DialogueHistoryEntry,
    DialogueHistoryStore,
    append_dialogue_exchange,
    format_dialogue_history_text,
    replay_latest_assistant,
    revert_latest_exchange,
)
from .engine import TICK_SECONDS, apply_action, apply_tick, create_initial_state, describe_goal
from .events import (
    ActionDomainEventRequest,
    CompanionEvent,
    DomainEventComposer,
    InventoryDomainEventRequest,
    ProactiveDomainEventRequest,
)
from .expression_diagnostics import ExpressionDiagnosticsService, fetch_provider_model_ids
from .expression_context import (
    CharacterProfileExpressionContextProvider,
    ExpressionContextChain,
    RuntimeExpressionContextService,
)
from .expression_event_pipeline import ExpressionEventPipeline
from .expression_settings import (
    ExpressionSettings,
    ExpressionSettingsStore,
    normalize_expression_settings,
)
from .inventory import InventoryService, InventoryUseRequest, ShopPurchaseRequest, ShopService, format_item_effect
from .memory import (
    LongTermMemoryEntry,
    LongTermMemoryService,
    LongTermMemoryStore,
    MemoryLogService,
    memory_kind_for_inventory_usage,
)
from .models import CompanionState
from .proactive_companion import ProactiveCompanionDecision, ProactiveCompanionService
from .relationship import RelationshipService
from .runtime_paths import (
    capability_settings_path as default_capability_settings_path,
    expression_settings_path as default_expression_settings_path,
    long_term_memory_path as default_long_term_memory_path,
)
from .session_goals import SessionGoalResult, SessionGoalTracker
from .snapshot import CompanionSnapshot, SnapshotBuilder, SnapshotContextFactory, format_delta_text
from .storage import DEFAULT_SAVE_PATH, SaveManager, logical_time_from_state

ExpressionContextProvider = Callable[[], dict[str, object]]


class CompanionSaveManager(Protocol):
    def load(self) -> CompanionState | None:
        ...

    def save(self, state: CompanionState) -> None:
        ...


class CompanionDialogueHistoryStore(Protocol):
    def load(self) -> tuple[DialogueHistoryEntry, ...]:
        ...

    def save(self, entries: Iterable[DialogueHistoryEntry]) -> None:
        ...

    def clear(self) -> None:
        ...


class CompanionExpressionSettingsStore(Protocol):
    def load(self) -> ExpressionSettings:
        ...

    def save(self, settings: ExpressionSettings) -> None:
        ...


class CompanionCapabilitySettingsStore(Protocol):
    def load(self) -> CapabilitySettings:
        ...

    def save(self, settings: CapabilitySettings) -> CapabilitySettings:
        ...


class CompanionLongTermMemoryStore(Protocol):
    def load(self) -> tuple[LongTermMemoryEntry, ...]:
        ...

    def save(self, entries: Iterable[LongTermMemoryEntry]) -> None:
        ...


class CompanionController:
    def __init__(
        self,
        save_path: Path | None = None,
        auto_load: bool = True,
        ai_expressor: ShinsekaiAIExpressor | None = None,
        expression_context_provider: ExpressionContextProvider | None = None,
        save_manager: CompanionSaveManager | None = None,
        dialogue_history_path: Path | None = None,
        dialogue_history_store: CompanionDialogueHistoryStore | None = None,
        expression_settings_path: Path | None = None,
        expression_settings_store: CompanionExpressionSettingsStore | None = None,
        capability_settings_path: Path | None = None,
        capability_settings_store: CompanionCapabilitySettingsStore | None = None,
        long_term_memory_path: Path | None = None,
        long_term_memory_store: CompanionLongTermMemoryStore | None = None,
        character_id: str = DEFAULT_CHARACTER_ID,
        character_resources: CharacterResources | None = None,
        user_data_root: Path | str | None = None,
    ) -> None:
        self._user_data_root = Path(user_data_root) if user_data_root is not None else None
        session_paths = (
            build_character_session_paths(character_id, user_data_root=self._user_data_root)
            if self._user_data_root is not None
            else None
        )
        self.resources = character_resources or load_character_resources(character_id)
        self.character_pack = self.resources.character_pack
        self.shop_items = self.resources.shop_items
        self.save_path = Path(save_path) if save_path is not None else (
            session_paths.save_path if session_paths is not None else DEFAULT_SAVE_PATH
        )
        self.save_manager = save_manager or SaveManager(
            self.save_path,
            inventory_item_ids=tuple(self.shop_items),
        )
        self.dialogue_history_path = (
            Path(dialogue_history_path)
            if dialogue_history_path is not None
            else (
                session_paths.dialogue_history_path
                if session_paths is not None
                else _dialogue_history_path_for_save_path(self.save_path)
            )
        )
        self.dialogue_history_store = dialogue_history_store or DialogueHistoryStore(self.dialogue_history_path)
        self.dialogue_history = self.dialogue_history_store.load()
        self.expression_settings_path = (
            Path(expression_settings_path)
            if expression_settings_path is not None
            else (
                session_paths.expression_settings_path
                if session_paths is not None
                else _expression_settings_path_for_save_path(self.save_path)
            )
        )
        self.expression_settings_store = expression_settings_store or ExpressionSettingsStore(
            self.expression_settings_path
        )
        self.expression_settings = self.expression_settings_store.load()
        self.capability_settings_path = (
            Path(capability_settings_path)
            if capability_settings_path is not None
            else _capability_settings_path_for_save_path(self.save_path)
        )
        self.capability_settings_store = capability_settings_store or CapabilitySettingsStore(
            self.capability_settings_path
        )
        self.capability_settings = self.capability_settings_store.load()
        self.long_term_memory_path = (
            Path(long_term_memory_path)
            if long_term_memory_path is not None
            else (
                session_paths.long_term_memory_path
                if session_paths is not None
                else _long_term_memory_path_for_save_path(self.save_path)
            )
        )
        self._long_term_memory_enabled = (
            auto_load
            or session_paths is not None
            or long_term_memory_path is not None
            or long_term_memory_store is not None
        )
        self.long_term_memory_store = long_term_memory_store or LongTermMemoryStore(self.long_term_memory_path)
        self.long_term_memory_service = LongTermMemoryService(
            self.long_term_memory_store.load() if self._long_term_memory_enabled else ()
        )
        self._perception_summary = ""
        self._tool_results: list[dict[str, object]] = []
        self._current_player_message = ""
        self.ai_expressor = ai_expressor or build_default_ai_expressor(
            settings=self.expression_settings if Path(self.expression_settings_path).exists() else None
        )
        self._closed = False
        self.expression_context_provider = expression_context_provider or ExpressionContextChain(
            [CharacterProfileExpressionContextProvider(self.character_pack)]
        )
        loaded_state = self.save_manager.load() if auto_load else None
        if loaded_state is not None and loaded_state.character_id != self.character_pack.character_id:
            loaded_state = None
        self.state = loaded_state or create_initial_state(
            now=0,
            character_id=self.character_pack.character_id,
            character_name=self.character_pack.name,
            buyable_items=self.shop_items,
        )
        if self.state.character_id == self.character_pack.character_id:
            self.state = replace(self.state, character_name=self.character_pack.name)
        self.now = logical_time_from_state(self.state) if loaded_state is not None else 0
        self.tick_count = 0
        self.last_motion = "Default"
        self.last_feedback = "信号稳定。先从一个简单动作开始。"
        self.last_delta_text = "暂无变化"
        self.last_allowed = True
        self.last_item_feedback_icon: str | None = None
        self.last_proactive_feedback: dict[str, str] | None = None
        self._last_proactive_at: dict[str, int] = {}
        self._proactive_daily_counts: dict[str, int] = {}
        self._force_next_proactive = False
        self._force_next_proactive_kind = ""
        self.session_goals = SessionGoalTracker()
        self.last_session_goal_reward: dict[str, object] | None = None
        self.last_events = self._build_events(effect="ATTENTION", include_ai_expression=False)
        if loaded_state is None:
            self._persist()

    def __enter__(self) -> "CompanionController":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        close = getattr(self.ai_expressor, "close", None)
        try:
            if callable(close):
                close()
        except Exception:
            pass
        finally:
            self._closed = True

    @property
    def user_data_root(self) -> Path | None:
        return self._user_data_root

    def reset_demo_state(self, *, include_ai_expression: bool = True) -> dict[str, object]:
        self.state = create_initial_state(
            now=0,
            character_id=self.character_pack.character_id,
            character_name=self.character_pack.name,
            buyable_items=self.shop_items,
        )
        if self.state.character_id == self.character_pack.character_id:
            self.state = replace(self.state, character_name=self.character_pack.name)
        self.now = 0
        self.tick_count = 0
        self.last_motion = "Default"
        self.last_feedback = f"演示状态已重置。{self.character_pack.name} 回到初识、空背包和 20 coins。"
        self.last_delta_text = "演示 seed 已重置"
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self._last_proactive_at.clear()
        self._proactive_daily_counts.clear()
        self._force_next_proactive = False
        self._force_next_proactive_kind = ""
        self.session_goals = SessionGoalTracker()
        self.last_session_goal_reward = None
        self.last_events = self._build_events(effect="SWITCH", include_ai_expression=include_ai_expression)
        self._persist()
        return self.get_snapshot()

    def get_snapshot(self) -> dict[str, object]:
        return self.get_typed_snapshot().to_compatible_dict()

    def get_typed_snapshot(self) -> CompanionSnapshot:
        builder_input = SnapshotContextFactory(
            state=self.state,
            character_title=self.character_pack.title,
            character_description=self.character_pack.description,
            current_motion=self.last_motion,
            motion_caption=resolve_motion_caption(
                self.character_pack,
                motion=self.last_motion,
                mode=self.state.mode,
                allowed=self.last_allowed,
            ),
            feedback=self.last_feedback,
            delta_text=self.last_delta_text,
            allowed=self.last_allowed,
            tick_count=self.tick_count,
            events=self.last_events,
            actions=self._build_actions(),
            shop_items=self._build_shop_items(),
            inventory_items=self._build_inventory_items(),
            item_feedback_icon=self.last_item_feedback_icon,
            proactive_feedback=self.last_proactive_feedback,
            dialogue_history=self.dialogue_history,
            long_term_memory=self.long_term_memory_service.summaries(),
            relationship_decorations=self.character_pack.relationship_decorations,
            session_goal=self.session_goals.snapshot(),
            next_suggested_action=self._next_session_goal_action(),
            session_goal_reward=self.last_session_goal_reward,
        ).build_input()
        return SnapshotBuilder(builder_input).build()

    def switch_character(
        self,
        character_id: str,
        *,
        pack_dir: Path | str | None = None,
        include_ai_expression: bool = False,
    ) -> dict[str, object]:
        if character_id == self.character_pack.character_id:
            return self.get_snapshot()

        resources = (
            load_character_resources_from_dir(pack_dir)
            if pack_dir is not None
            else load_character_resources(character_id)
        )
        if resources.character_pack.character_id != character_id:
            raise ValueError("character pack id does not match selected character")
        session_paths = build_character_session_paths(character_id, user_data_root=self._user_data_root)
        self.resources = resources
        self.character_pack = resources.character_pack
        self.shop_items = resources.shop_items
        self.save_path = session_paths.save_path
        self.save_manager = SaveManager(self.save_path, inventory_item_ids=tuple(self.shop_items))
        self.dialogue_history_path = session_paths.dialogue_history_path
        self.dialogue_history_store = DialogueHistoryStore(self.dialogue_history_path)
        self.dialogue_history = self.dialogue_history_store.load()
        self.expression_settings_path = session_paths.expression_settings_path
        self.expression_settings_store = ExpressionSettingsStore(self.expression_settings_path)
        self.expression_settings = self.expression_settings_store.load()
        self.long_term_memory_path = session_paths.long_term_memory_path
        self._long_term_memory_enabled = True
        self.long_term_memory_store = LongTermMemoryStore(self.long_term_memory_path)
        self.long_term_memory_service = LongTermMemoryService(self.long_term_memory_store.load())
        self.expression_context_provider = ExpressionContextChain(
            [CharacterProfileExpressionContextProvider(self.character_pack)]
        )
        self._replace_ai_expressor(
            build_default_ai_expressor(
                settings=self.expression_settings if Path(self.expression_settings_path).exists() else None
            )
        )
        loaded_state = self.save_manager.load()
        if loaded_state is not None and loaded_state.character_id != self.character_pack.character_id:
            loaded_state = None
        self.state = loaded_state or create_initial_state(
            now=0,
            character_id=self.character_pack.character_id,
            character_name=self.character_pack.name,
            buyable_items=self.shop_items,
        )
        if self.state.character_id == self.character_pack.character_id:
            self.state = replace(self.state, character_name=self.character_pack.name)
        self.now = logical_time_from_state(self.state) if loaded_state is not None else 0
        self.tick_count = 0
        self.last_motion = "Default"
        self.last_feedback = f"已切换到 {self.character_pack.name}。"
        self.last_delta_text = "角色会话已切换"
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self.last_session_goal_reward = None
        self._perception_summary = ""
        self._tool_results = []
        self.session_goals = SessionGoalTracker()
        self.last_events = self._build_events(effect="SWITCH", include_ai_expression=include_ai_expression)
        if loaded_state is None:
            self._persist()
        return self.get_snapshot()

    def perform_action(self, action_id: str, *, include_ai_expression: bool = True) -> dict[str, object]:
        return self.perform_action_request(
            CompanionActionRequest(action_id=action_id, source="control_panel"),
            include_ai_expression=include_ai_expression,
        )

    def submit_dialogue_request(
        self,
        request: DialogueRequest,
        *,
        include_ai_expression: bool = False,
    ) -> dict[str, object]:
        text = request.normalized_text()
        self.last_motion = "Default"
        if text:
            self.last_feedback = f"我听见了：{text}"
            self.last_delta_text = "对话输入不改变养成状态"
        else:
            self.last_feedback = "我在这里。你可以慢慢说。"
            self.last_delta_text = "空白对话未改变养成状态"
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self.last_session_goal_reward = None
        self._current_player_message = text
        try:
            self.last_events = self._build_events(effect="ATTENTION", include_ai_expression=include_ai_expression)
        finally:
            self._current_player_message = ""
        if text:
            assistant_text = _assistant_dialogue_text_from_events(
                self.last_events,
                character_name=self.state.character_name,
                fallback=self.last_feedback,
            )
            self.dialogue_history = append_dialogue_exchange(
                self.dialogue_history,
                user_text=text,
                assistant_name=self.state.character_name,
                assistant_text=assistant_text,
                effect="ATTENTION",
                source=request.source,
            )
            self.dialogue_history_store.save(self.dialogue_history)
        self._persist()
        return self.get_snapshot()

    def copy_dialogue_history_text(self) -> str:
        return format_dialogue_history_text(self.dialogue_history)

    def get_expression_settings(self, *, include_api_key: bool = False) -> dict[str, object]:
        return self.expression_settings.to_dict(include_api_key=include_api_key)

    def update_expression_settings(self, settings: ExpressionSettings | dict[str, object]) -> dict[str, object]:
        normalized = settings if isinstance(settings, ExpressionSettings) else normalize_expression_settings(settings)
        self.expression_settings = normalized
        self.expression_settings_store.save(normalized)
        self._replace_ai_expressor(build_default_ai_expressor(settings=normalized))
        return normalized.to_public_dict()

    def get_capability_settings(self) -> CapabilitySettings:
        return self.capability_settings

    def update_capability_settings(self, settings: CapabilitySettings | dict[str, object]) -> CapabilitySettings:
        normalized = settings if isinstance(settings, CapabilitySettings) else CapabilitySettings.from_dict(settings)
        self.capability_settings = self.capability_settings_store.save(normalized)
        return self.capability_settings

    def set_player_alias(self, alias: str, *, include_ai_expression: bool = False) -> dict[str, object]:
        normalized = RelationshipService(self.state).set_player_alias(alias)
        self.last_motion = "Default"
        if normalized:
            self.last_feedback = f"我记住这个称呼了：{normalized}"
        else:
            self.last_feedback = "本地称呼已清空。"
        self.last_delta_text = "本地称呼更新，不改变成长数值"
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self.last_events = self._build_events(effect="SWITCH", include_ai_expression=include_ai_expression)
        self._persist()
        return self.get_snapshot()

    def set_perception_summary(self, summary: str) -> None:
        self._perception_summary = summary if isinstance(summary, str) else ""

    def set_tool_results(self, results: list[dict[str, object]]) -> None:
        self._tool_results = list(results) if isinstance(results, list) else []

    def upsert_long_term_memory(
        self,
        *,
        key: str,
        category: str,
        summary: str,
        source: str = "local_api",
    ) -> dict[str, object]:
        self._upsert_long_term_memory(
            key=key,
            category=category,
            summary=summary,
            source=source,
            now=self.now,
        )
        return self.get_snapshot()

    def test_expression_provider(self) -> dict[str, object]:
        return self._expression_diagnostics().test_provider().to_public_dict()

    def fetch_expression_models(
        self,
        settings: ExpressionSettings | dict[str, object] | None = None,
    ) -> tuple[str, ...]:
        return self._expression_diagnostics().fetch_models(settings)

    def clear_dialogue_history(self) -> dict[str, object]:
        self.dialogue_history = ()
        self.dialogue_history_store.clear()
        self._set_dialogue_history_feedback(
            feedback="对话已清屏。",
            delta_text="对话历史已清空，养成状态未改变",
            effect="SWITCH",
        )
        return self.get_snapshot()

    def replay_latest_dialogue(self) -> dict[str, object]:
        entry = replay_latest_assistant(self.dialogue_history)
        if entry is None:
            self._set_dialogue_history_feedback(
                feedback="暂无可回放的对话。",
                delta_text="历史回放未改变养成状态",
                effect="DISAPPOINTED",
            )
            return self.get_snapshot()
        self._set_dialogue_history_feedback(
            feedback=entry.text,
            delta_text="历史回放不改变养成状态",
            effect=entry.effect or "ATTENTION",
        )
        return self.get_snapshot()

    def revert_dialogue_history(self) -> dict[str, object]:
        self.dialogue_history, entry = revert_latest_exchange(self.dialogue_history)
        self.dialogue_history_store.save(self.dialogue_history)
        if entry is None:
            self._set_dialogue_history_feedback(
                feedback="已回溯到对话开始。",
                delta_text="历史回溯不改变养成状态",
                effect="SWITCH",
            )
            return self.get_snapshot()
        self._set_dialogue_history_feedback(
            feedback=entry.text,
            delta_text="历史回溯不改变养成状态",
            effect=entry.effect or "ATTENTION",
        )
        return self.get_snapshot()

    def perform_action_request(
        self,
        request: CompanionActionRequest,
        *,
        include_ai_expression: bool = True,
    ) -> dict[str, object]:
        action_id = request.action_id
        self.now += 5
        previous_unlocks = set(self.state.unlocks)
        result = apply_action(self.state, action_id=action_id, now=self.now)
        self.state = result.state
        self.last_motion = result.motion
        self.last_feedback = result.feedback["speech"]
        self.last_delta_text = format_delta_text(result.delta)
        self.last_allowed = result.allowed
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self.last_session_goal_reward = None
        new_unlocks = self._new_relationship_unlocks(previous_unlocks)
        unlock_feedback = self._relationship_unlock_feedback(new_unlocks)
        if unlock_feedback:
            self.last_feedback = f"{self.last_feedback} {unlock_feedback}"
        memory_summary = None
        if result.allowed:
            memory_summary = f"{self._action_label(action_id)}：{self.last_feedback}"
            self._remember(kind="互动", summary=memory_summary, motion=result.motion)
            self._remember_relationship_unlocks(new_unlocks)
            self._settle_session_goal_event("action", action_id=action_id)
        event_bundle = DomainEventComposer(self.state).action_events(
            ActionDomainEventRequest(
                action_id=action_id,
                motion=result.motion,
                feedback=self.last_feedback,
                allowed=result.allowed,
                mode=self.state.mode,
                memory_kind="互动" if result.allowed else None,
                memory_summary=memory_summary,
                relationship_unlocks=self._relationship_event_payloads(new_unlocks),
            )
        )
        self.last_events = self._build_events(
            effect=event_bundle.effect,
            domain_events=event_bundle.events,
            include_ai_expression=include_ai_expression,
        )
        self._persist()
        return self.get_snapshot()

    def buy_selected_item(self, item_id: str, *, include_ai_expression: bool = True) -> dict[str, object]:
        return self.buy_item_request(
            ShopPurchaseRequest(item_id=item_id),
            include_ai_expression=include_ai_expression,
        )

    def purchase_shop_item(self, item_id: str, *, include_ai_expression: bool = True) -> dict[str, object]:
        return self.buy_selected_item(item_id, include_ai_expression=include_ai_expression)

    def buy_item_request(
        self,
        request: ShopPurchaseRequest,
        *,
        include_ai_expression: bool = True,
    ) -> dict[str, object]:
        self.state = ShopService(self.state, self._item_icon_path, self.shop_items).purchase(request)
        item_id = request.item_id
        item = self.shop_items[item_id]
        self.last_motion = "Shop"
        self.last_feedback = f"已购买：{item.name}。放进背包里了。"
        self.last_delta_text = f"coins -{item.price}"
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self.last_session_goal_reward = None
        event_bundle = DomainEventComposer(self.state).inventory_events(
            InventoryDomainEventRequest(
                motion=self.last_motion,
                feedback=self.last_feedback,
                base_effect="SWITCH",
                item_id=item_id,
                action="purchase",
                item_name=item.name,
                icon_path=self._item_icon_path(item),
            )
        )
        self.last_events = self._build_events(
            effect=event_bundle.effect,
            domain_events=event_bundle.events,
            include_ai_expression=include_ai_expression,
        )
        self._persist()
        return self.get_snapshot()

    def use_selected_item(
        self,
        item_id: str,
        usage: str,
        *,
        include_ai_expression: bool = True,
    ) -> dict[str, object]:
        return self.use_inventory_request(
            InventoryUseRequest(item_id=item_id, usage=usage),
            include_ai_expression=include_ai_expression,
        )

    def use_inventory_item(
        self,
        item_id: str,
        usage: str,
        *,
        include_ai_expression: bool = True,
    ) -> dict[str, object]:
        return self.use_selected_item(item_id, usage, include_ai_expression=include_ai_expression)

    def use_inventory_request(
        self,
        request: InventoryUseRequest,
        *,
        include_ai_expression: bool = True,
    ) -> dict[str, object]:
        self.now += 5
        item_id = request.item_id
        usage = request.usage
        item = self.shop_items[item_id]
        previous_unlocks = set(self.state.unlocks)
        try:
            self.state = InventoryService(self.state, self._item_icon_path, self.shop_items).use(request, now=self.now)
        except ValueError as exc:
            self.last_motion = "SwitchDown"
            self.last_feedback = str(exc)
            self.last_delta_text = "数值无变化"
            self.last_allowed = False
            self.last_item_feedback_icon = None
            self.last_proactive_feedback = None
            self.last_session_goal_reward = None
            event_bundle = DomainEventComposer(self.state).action_events(
                ActionDomainEventRequest(
                    action_id=usage,
                    motion=self.last_motion,
                    feedback=self.last_feedback,
                    allowed=False,
                    mode=self.state.mode,
                )
            )
            self.last_events = self._build_events(
                effect=event_bundle.effect,
                domain_events=event_bundle.events,
                include_ai_expression=include_ai_expression,
            )
            self._persist()
            return self.get_snapshot()
        if usage == "feed":
            self.last_motion = "Eat"
            self.last_feedback = f"投喂了 {item.name}。她的频率平稳了一点。"
        elif usage == "gift":
            self.last_motion = "Gift"
            self.last_feedback = f"赠送了 {item.name}。她把这份心意收下了。"
        else:
            self.last_motion = "UseItem"
            self.last_feedback = f"使用了 {item.name}。"
        new_unlocks = self._new_relationship_unlocks(previous_unlocks)
        unlock_feedback = self._relationship_unlock_feedback(new_unlocks)
        if unlock_feedback:
            self.last_feedback = f"{self.last_feedback} {unlock_feedback}"
        self.last_delta_text = format_item_effect(item_id, usage, self.shop_items)
        self.last_allowed = True
        self.last_item_feedback_icon = self._item_icon_path(item)
        self.last_proactive_feedback = None
        self.last_session_goal_reward = None
        memory_kind = memory_kind_for_inventory_usage(usage)
        memory_summary = f"{memory_kind}了 {item.name}：{self.last_delta_text}"
        self._remember(
            kind=memory_kind,
            summary=memory_summary,
            motion=self.last_motion,
            item_id=item_id,
        )
        self._remember_relationship_unlocks(new_unlocks)
        self._settle_session_goal_event("inventory", action_id=usage)
        base_effect = "ATTENTION" if usage in {"feed", "gift"} else "SWITCH"
        event_bundle = DomainEventComposer(self.state).inventory_events(
            InventoryDomainEventRequest(
                motion=self.last_motion,
                feedback=self.last_feedback,
                base_effect=base_effect,
                item_id=item_id,
                action=usage,
                item_name=item.name,
                icon_path=self._item_icon_path(item),
                memory_kind=memory_kind,
                memory_summary=memory_summary,
                relationship_unlocks=self._relationship_event_payloads(new_unlocks),
            )
        )
        self.last_events = self._build_events(
            effect=event_bundle.effect,
            domain_events=event_bundle.events,
            include_ai_expression=include_ai_expression,
        )
        self._persist()
        return self.get_snapshot()

    def advance_tick(self, *, include_ai_expression: bool = True) -> dict[str, object]:
        self.now += TICK_SECONDS
        self.tick_count += 1
        previous_unlocks = set(self.state.unlocks)
        previous_state = self.state
        self.state = apply_tick(self.state, ticks=1, now=self.now)
        self.last_motion = "Tick"
        self.last_feedback = "时间过去了 15 秒。她还在持续变化。"
        new_unlocks = self._new_relationship_unlocks(previous_unlocks)
        unlock_feedback = self._relationship_unlock_feedback(new_unlocks)
        if unlock_feedback:
            self.last_feedback = f"{self.last_feedback} {unlock_feedback}"
        self.last_delta_text = "tick -15s"
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_session_goal_reward = None
        proactive_decision = self._select_proactive_decision(previous_state)
        self.last_proactive_feedback = proactive_decision.to_legacy_feedback()
        if proactive_decision.feedback:
            self.last_feedback = proactive_decision.feedback.speech
            self._last_proactive_at.update(proactive_decision.cooldown_updates())
            for key, count in proactive_decision.daily_count_updates().items():
                self._proactive_daily_counts[key] = self._proactive_daily_counts.get(key, 0) + count
            MemoryLogService(self.state.memory_log).append_drafts(
                at=self.now,
                drafts=proactive_decision.memory_drafts(),
            )
        self._remember_relationship_unlocks(new_unlocks)
        event_bundle = DomainEventComposer(self.state).proactive_events(
            ProactiveDomainEventRequest(
                motion=self.last_motion,
                feedback=self.last_feedback,
                base_effect=proactive_decision.effect,
                proactive_payload=proactive_decision.event_payload(),
                relationship_unlocks=self._relationship_event_payloads(new_unlocks),
            )
        )
        self.last_events = self._build_events(
            effect=event_bundle.effect,
            domain_events=event_bundle.events,
            include_ai_expression=include_ai_expression,
        )
        self._persist()
        return self.get_snapshot()

    def trigger_demo_proactive(self, scenario: str, *, include_ai_expression: bool = True) -> dict[str, object]:
        if scenario == "low_charge":
            forced_kind = "low_charge"
            self.state.charge = 25
            self.state.focus = max(self.state.focus, 70)
            self.state.stability = max(self.state.stability, 70)
            self.state.mood = max(self.state.mood, 60)
            self._last_proactive_at.pop("low_charge", None)
        elif scenario == "quiet_mood":
            forced_kind = "low_mood"
            self.now = max(self.now, self.state.last_interaction_at + 61)
            self.state.charge = max(self.state.charge, 80)
            self.state.focus = max(self.state.focus, 80)
            self.state.stability = max(self.state.stability, 80)
            self.state.mood = 35
            self._last_proactive_at.pop("low_mood", None)
        elif scenario == "morning":
            forced_kind = "morning_greeting"
            self.now = max(self.now, 8 * 3600 - TICK_SECONDS)
            self.state.charge = max(self.state.charge, 80)
            self.state.focus = max(self.state.focus, 70)
            self.state.stability = max(self.state.stability, 70)
            self._last_proactive_at.pop("morning_greeting", None)
        elif scenario == "high_trust":
            forced_kind = "high_trust"
            self.state.trust = 34.9
            self.state.mood = max(self.state.mood, 80)
            self.state.charge = max(self.state.charge, 80)
            self.state.focus = max(self.state.focus, 80)
            self._last_proactive_at.pop("high_trust", None)
        elif scenario == "return_idle":
            forced_kind = "return_after_idle"
            self.now = max(self.now, self.state.last_interaction_at + 300 - TICK_SECONDS)
            self.state.charge = max(self.state.charge, 80)
            self.state.focus = max(self.state.focus, 80)
            self.state.stability = max(self.state.stability, 80)
            self.state.mood = max(self.state.mood, 60)
            self._last_proactive_at.pop("return_after_idle", None)
        elif scenario == "post_gift":
            forced_kind = "post_gift"
            self.state.last_gift_at = self.now
            self.state.last_gift_item_id = "demo_gift"
            self.state.charge = max(self.state.charge, 80)
            self.state.focus = max(self.state.focus, 80)
            self.state.stability = max(self.state.stability, 80)
            self._last_proactive_at.pop("post_gift", None)
        else:
            raise ValueError(f"Unknown demo proactive scenario: {scenario}")
        self._force_next_proactive = True
        self._force_next_proactive_kind = forced_kind
        return self.advance_tick(include_ai_expression=include_ai_expression)

    def _persist(self) -> None:
        self.save_manager.save(self.state)

    def _replace_ai_expressor(self, next_expressor: ShinsekaiAIExpressor) -> None:
        current = self.ai_expressor
        if current is not next_expressor:
            close = getattr(current, "close", None)
            try:
                if callable(close):
                    close()
            except Exception:
                pass
        self.ai_expressor = next_expressor

    def _expression_diagnostics(self) -> ExpressionDiagnosticsService:
        return ExpressionDiagnosticsService(
            settings=self.expression_settings,
            expressor=self.ai_expressor,
            state_provider=lambda: self.state,
            snapshot_provider=self.get_typed_snapshot,
            context_provider=self._expression_context,
            choices_provider=lambda: tuple(entry["label"] for entry in self._build_actions()),
            model_fetcher=fetch_provider_model_ids,
        )

    def _set_dialogue_history_feedback(self, *, feedback: str, delta_text: str, effect: str) -> None:
        self.last_motion = "Default"
        self.last_feedback = feedback
        self.last_delta_text = delta_text
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self.last_events = self._build_events(effect=effect, include_ai_expression=False)

    def _build_events(
        self,
        effect: str,
        domain_events: list[CompanionEvent] | None = None,
        *,
        include_ai_expression: bool = True,
    ) -> list[CompanionEvent]:
        return ExpressionEventPipeline(
            state=self.state,
            expressor=self.ai_expressor,
            snapshot_provider=self.get_typed_snapshot,
            context_provider=self._expression_context,
            actions_provider=self._build_actions,
        ).build_events(
            effect=effect,
            feedback=self.last_feedback,
            domain_events=domain_events,
            include_ai_expression=include_ai_expression,
            closed=self._closed,
        )

    def _build_actions(self) -> list[dict[str, object]]:
        return [action.to_legacy_dict() for action in CompanionActionLayer(self.state).available_actions()]

    def _build_shop_items(self) -> list[dict[str, object]]:
        return [
            item.to_legacy_dict()
            for item in ShopService(self.state, self._item_icon_path, self.shop_items).shop_items()
        ]

    def _build_inventory_items(self) -> list[dict[str, object]]:
        return [
            item.to_legacy_dict()
            for item in InventoryService(self.state, self._item_icon_path, self.shop_items).inventory_items()
        ]

    def _next_session_goal_action(self) -> dict[str, object] | None:
        suggested = self.session_goals.suggested_action()
        for action in self._build_actions():
            if action.get("action_id") == suggested["action_id"]:
                return dict(action)
        return suggested

    def _settle_session_goal_event(self, event_type: str, *, action_id: str) -> SessionGoalResult:
        result = self.session_goals.record_event(event_type, action_id=action_id)
        reward = result.to_public_dict()
        self.last_session_goal_reward = reward
        if reward:
            self.state.coins += int(reward.get("coins", 0))
            self.state.exp += int(reward.get("exp", 0))
        return result

    def _expression_context(self) -> dict[str, object]:
        context = RuntimeExpressionContextService(
            state=self.state,
            relationship_decorations=self.character_pack.relationship_decorations,
            external_provider=self.expression_context_provider,
            perception_summary=self._perception_summary,
            tool_results=self._tool_results,
        )()
        if self._current_player_message:
            context["player_message"] = self._current_player_message
        return context

    def _item_icon_path(self, item) -> str:
        if not item.icon:
            return ""
        return str(self.resources.asset_dir / item.icon)

    def _remember(self, kind: str, summary: str, motion: str, item_id: str | None = None) -> None:
        MemoryLogService(self.state.memory_log).append(
            at=self.now,
            kind=kind,
            summary=summary,
            motion=motion,
            item_id=item_id,
        )

    def _action_label(self, action_id: str) -> str:
        return action_label(action_id)

    def _new_relationship_unlocks(self, previous_unlocks: set[str]) -> list[str]:
        return RelationshipService(self.state).new_unlocks(previous_unlocks)

    def _relationship_unlock_feedback(self, unlocks: list[str]) -> str:
        return RelationshipService(self.state).unlock_feedback(unlocks)

    def _remember_relationship_unlocks(self, unlocks: list[str]) -> None:
        MemoryLogService(self.state.memory_log).append_drafts(
            at=self.now,
            drafts=RelationshipService(self.state).unlock_memory_drafts(unlocks, motion=self.last_motion),
        )
        for payload in RelationshipService(self.state).unlock_event_payloads(unlocks):
            self._upsert_long_term_memory(
                key=f"relationship:{payload['unlock_id']}",
                category="relationship_unlock",
                summary=payload["message"],
                source="relationship_unlock",
                now=self.now,
            )

    def _upsert_long_term_memory(
        self,
        *,
        key: str,
        category: str,
        summary: str,
        source: str,
        now: int,
    ) -> None:
        if not self._long_term_memory_enabled:
            return
        self.long_term_memory_service.upsert(
            key=key,
            category=category,
            summary=summary,
            source=source,
            now=now,
        )
        self.long_term_memory_store.save(self.long_term_memory_service.entries)

    def _relationship_event_payloads(self, unlocks: list[str]) -> list[dict[str, str]]:
        return RelationshipService(self.state).unlock_event_payloads(unlocks)

    def _select_proactive_decision(self, previous_state: CompanionState) -> ProactiveCompanionDecision:
        settings = self.capability_settings.proactive_companion
        forced_kind = ""
        if self._force_next_proactive:
            forced_kind = self._force_next_proactive_kind
            settings = replace(
                settings,
                enabled=True,
                interval_seconds=60,
                global_cooldown_seconds=60,
                daily_limit=max(settings.daily_limit, 1),
                quiet_hours_enabled=False,
            )
            self._force_next_proactive = False
            self._force_next_proactive_kind = ""
        expression_context = self._expression_context()
        return ProactiveCompanionService(
            state=self.state,
            previous_state=previous_state,
            now=self.now,
            settings=settings,
            last_proactive_at=self._last_proactive_at,
            daily_counts=self._proactive_daily_counts,
            perception_summary=str(expression_context.get("perception_summary", "")),
            tool_results=expression_context.get("tool_results", []),
            forced_kind=forced_kind,
        ).select_decision(motion=self.last_motion)


def _dialogue_history_path_for_save_path(save_path: Path) -> Path:
    if save_path.name == "companion_save.json":
        return save_path.with_name("dialogue_history.json")
    if save_path.name == "companion_demo_save.json":
        return save_path.with_name("companion_demo_dialogue_history.json")
    return save_path.with_name(f"{save_path.stem}_dialogue_history.json")


def _expression_settings_path_for_save_path(save_path: Path) -> Path:
    if save_path.name == "companion_save.json":
        return default_expression_settings_path()
    if save_path.name == "companion_demo_save.json":
        return save_path.with_name("companion_demo_expression_settings.json")
    return save_path.with_name(f"{save_path.stem}_expression_settings.json")


def _capability_settings_path_for_save_path(save_path: Path) -> Path:
    if save_path.name == "companion_save.json":
        return default_capability_settings_path()
    if save_path.name == "companion_demo_save.json":
        return save_path.with_name("companion_demo_capability_settings.json")
    return save_path.with_name(f"{save_path.stem}_capability_settings.json")


def _long_term_memory_path_for_save_path(save_path: Path) -> Path:
    if save_path.name == "companion_save.json":
        return default_long_term_memory_path()
    if save_path.name == "companion_demo_save.json":
        return save_path.with_name("companion_demo_long_term_memory.json")
    return save_path.with_name(f"{save_path.stem}_long_term_memory.json")


def _assistant_dialogue_text_from_events(
    events: list[CompanionEvent],
    *,
    character_name: str,
    fallback: str,
) -> str:
    for event in events:
        if event.event_type == "speech" and event.character_name == character_name and event.speech.strip():
            return event.speech
    return fallback
