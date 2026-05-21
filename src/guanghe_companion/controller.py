from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from .actions import CompanionActionLayer, CompanionActionRequest, action_label
from .ai_expressor import ExpressionRequest, ShinsekaiAIExpressor, build_default_ai_expressor
from .character_pack import ASSETS_ROOT, load_default_character_pack, resolve_motion_caption
from .engine import BUYABLE_ITEMS, TICK_SECONDS, apply_action, apply_tick, create_initial_state, describe_goal
from .events import (
    ActionDomainEventRequest,
    CompanionEvent,
    DomainEventComposer,
    EventValidator,
    InventoryDomainEventRequest,
    ProactiveDomainEventRequest,
    build_typed_fallback_events,
)
from .expression_context import CharacterProfileExpressionContextProvider, ExpressionContextChain
from .inventory import InventoryService, InventoryUseRequest, ShopPurchaseRequest, ShopService, format_item_effect
from .memory import MemoryLogService, memory_kind_for_inventory_usage
from .models import CompanionState
from .relationship import ProactiveCompanionDecision, ProactiveCompanionService, RelationshipService
from .snapshot import CompanionSnapshot, SnapshotBuilder, SnapshotContextFactory, format_delta_text
from .storage import DEFAULT_SAVE_PATH, SaveManager, logical_time_from_state

ExpressionContextProvider = Callable[[], dict[str, object]]


class CompanionSaveManager(Protocol):
    def load(self) -> CompanionState | None:
        ...

    def save(self, state: CompanionState) -> None:
        ...


class CompanionController:
    def __init__(
        self,
        save_path: Path | None = None,
        auto_load: bool = True,
        ai_expressor: ShinsekaiAIExpressor | None = None,
        expression_context_provider: ExpressionContextProvider | None = None,
        save_manager: CompanionSaveManager | None = None,
    ) -> None:
        self.save_path = Path(save_path) if save_path is not None else DEFAULT_SAVE_PATH
        self.save_manager = save_manager or SaveManager(self.save_path)
        self.character_pack = load_default_character_pack()
        self.ai_expressor = ai_expressor or build_default_ai_expressor()
        self._closed = False
        self.expression_context_provider = expression_context_provider or ExpressionContextChain(
            [CharacterProfileExpressionContextProvider(self.character_pack)]
        )
        loaded_state = self.save_manager.load() if auto_load else None
        self.state = loaded_state or create_initial_state(now=0)
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

    def reset_demo_state(self, *, include_ai_expression: bool = True) -> dict[str, object]:
        self.state = create_initial_state(now=0)
        if self.state.character_id == self.character_pack.character_id:
            self.state = replace(self.state, character_name=self.character_pack.name)
        self.now = 0
        self.tick_count = 0
        self.last_motion = "Default"
        self.last_feedback = "演示状态已重置。星汐回到初识、空背包和 20 coins。"
        self.last_delta_text = "演示 seed 已重置"
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self._last_proactive_at.clear()
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
        ).build_input()
        return SnapshotBuilder(builder_input).build()

    def perform_action(self, action_id: str, *, include_ai_expression: bool = True) -> dict[str, object]:
        return self.perform_action_request(
            CompanionActionRequest(action_id=action_id, source="control_panel"),
            include_ai_expression=include_ai_expression,
        )

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
        new_unlocks = self._new_relationship_unlocks(previous_unlocks)
        unlock_feedback = self._relationship_unlock_feedback(new_unlocks)
        if unlock_feedback:
            self.last_feedback = f"{self.last_feedback} {unlock_feedback}"
        memory_summary = None
        if result.allowed:
            memory_summary = f"{self._action_label(action_id)}：{self.last_feedback}"
            self._remember(kind="互动", summary=memory_summary, motion=result.motion)
            self._remember_relationship_unlocks(new_unlocks)
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

    def buy_item_request(
        self,
        request: ShopPurchaseRequest,
        *,
        include_ai_expression: bool = True,
    ) -> dict[str, object]:
        self.state = ShopService(self.state, self._item_icon_path).purchase(request)
        item_id = request.item_id
        item = BUYABLE_ITEMS[item_id]
        self.last_motion = "Shop"
        self.last_feedback = f"已购买：{item.name}。放进背包里了。"
        self.last_delta_text = f"coins -{item.price}"
        self.last_allowed = True
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
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

    def use_inventory_request(
        self,
        request: InventoryUseRequest,
        *,
        include_ai_expression: bool = True,
    ) -> dict[str, object]:
        self.now += 5
        item_id = request.item_id
        usage = request.usage
        item = BUYABLE_ITEMS[item_id]
        previous_unlocks = set(self.state.unlocks)
        try:
            self.state = InventoryService(self.state, self._item_icon_path).use(request, now=self.now)
        except ValueError as exc:
            self.last_motion = "SwitchDown"
            self.last_feedback = str(exc)
            self.last_delta_text = "数值无变化"
            self.last_allowed = False
            self.last_item_feedback_icon = None
            self.last_proactive_feedback = None
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
        self.last_delta_text = format_item_effect(item_id, usage)
        self.last_allowed = True
        self.last_item_feedback_icon = self._item_icon_path(item)
        self.last_proactive_feedback = None
        memory_kind = memory_kind_for_inventory_usage(usage)
        memory_summary = f"{memory_kind}了 {item.name}：{self.last_delta_text}"
        self._remember(
            kind=memory_kind,
            summary=memory_summary,
            motion=self.last_motion,
            item_id=item_id,
        )
        self._remember_relationship_unlocks(new_unlocks)
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
        proactive_decision = self._select_proactive_decision(previous_state)
        self.last_proactive_feedback = proactive_decision.to_legacy_feedback()
        if proactive_decision.feedback:
            self.last_feedback = proactive_decision.feedback.speech
            self._last_proactive_at.update(proactive_decision.cooldown_updates())
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
            self.state.charge = 25
            self.state.focus = max(self.state.focus, 70)
            self.state.stability = max(self.state.stability, 70)
            self.state.mood = max(self.state.mood, 60)
            self._last_proactive_at.pop("low_charge", None)
        elif scenario == "quiet_mood":
            self.now = max(self.now, self.state.last_interaction_at + 61)
            self.state.charge = max(self.state.charge, 80)
            self.state.focus = max(self.state.focus, 80)
            self.state.stability = max(self.state.stability, 80)
            self.state.mood = 35
            self._last_proactive_at.pop("low_mood", None)
        else:
            raise ValueError(f"Unknown demo proactive scenario: {scenario}")
        return self.advance_tick(include_ai_expression=include_ai_expression)

    def _persist(self) -> None:
        self.save_manager.save(self.state)

    def _build_events(
        self,
        effect: str,
        domain_events: list[CompanionEvent] | None = None,
        *,
        include_ai_expression: bool = True,
    ) -> list[CompanionEvent]:
        actions = self._build_actions()
        choices = [entry["label"] for entry in actions]
        fallback_events = build_typed_fallback_events(
            state=self.state,
            feedback=self.last_feedback,
            choices=choices,
            effect=effect,
        )
        if self._closed or not include_ai_expression:
            return fallback_events + list(domain_events or [])
        expression_request = ExpressionRequest.from_snapshot(
            self.get_typed_snapshot(),
            context=self._expression_context(),
        )
        try:
            expressed_events = self.ai_expressor.express(expression_request, effect=effect)
        except Exception:
            return fallback_events + list(domain_events or [])
        if not expressed_events:
            return fallback_events + list(domain_events or [])
        if expressed_events == [event.to_legacy_dict() for event in fallback_events]:
            return fallback_events + list(domain_events or [])
        validated_events = EventValidator(self.state).validate(
            events=expressed_events,
            fallback_feedback=self.last_feedback,
            choices=choices,
        )
        if _is_local_fallback_expression(validated_events, self.last_feedback):
            return fallback_events + list(domain_events or [])
        local_context_events = [event for event in fallback_events if event.event_type in {"stat", "choice"}]
        expression_events = [event for event in validated_events if event.event_type == "speech"]
        if not expression_events:
            return fallback_events + list(domain_events or [])
        return expression_events[:1] + local_context_events + list(domain_events or [])

    def _build_actions(self) -> list[dict[str, object]]:
        return [action.to_legacy_dict() for action in CompanionActionLayer(self.state).available_actions()]

    def _build_shop_items(self) -> list[dict[str, object]]:
        return [item.to_legacy_dict() for item in ShopService(self.state, self._item_icon_path).shop_items()]

    def _build_inventory_items(self) -> list[dict[str, object]]:
        return [item.to_legacy_dict() for item in InventoryService(self.state, self._item_icon_path).inventory_items()]

    def _expression_context(self) -> dict[str, object]:
        if self.expression_context_provider is None:
            return {}
        try:
            external_context = self.expression_context_provider()
        except Exception:
            return {}
        if not isinstance(external_context, dict):
            return {}
        context: dict[str, object] = {}
        for key in ("perception_summary", "tool_results"):
            if key in external_context:
                context[key] = external_context[key]
        return context

    def _item_icon_path(self, item) -> str:
        if not item.icon:
            return ""
        return str(ASSETS_ROOT / self.character_pack.character_id / item.icon)

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

    def _relationship_event_payloads(self, unlocks: list[str]) -> list[dict[str, str]]:
        return RelationshipService(self.state).unlock_event_payloads(unlocks)

    def _select_proactive_decision(self, previous_state: CompanionState) -> ProactiveCompanionDecision:
        return ProactiveCompanionService(
            state=self.state,
            previous_state=previous_state,
            now=self.now,
            last_proactive_at=self._last_proactive_at,
        ).select_decision(motion=self.last_motion)


def _is_local_fallback_expression(events: list[CompanionEvent], feedback: str) -> bool:
    return [event.event_type for event in events] == ["speech", "stat", "choice"] and events[0].speech == feedback
