from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from .character_pack import load_default_character_pack, resolve_motion_caption
from .engine import BUYABLE_ITEMS, TICK_SECONDS, apply_action, apply_tick, create_initial_state, describe_goal, purchase_item, use_inventory_item
from .events import build_fallback_events, validate_events
from .models import CompanionState
from .storage import DEFAULT_SAVE_PATH, load_state, save_state


@dataclass(frozen=True, slots=True)
class ActionSpec:
    action_id: str
    label: str
    motion: str


ACTION_SPECS: tuple[ActionSpec, ...] = (
    ActionSpec("touch", "轻触", "TouchHead"),
    ActionSpec("soothe", "安抚", "Comfort"),
    ActionSpec("rest", "休息", "Sleep"),
    ActionSpec("study", "共同学习", "Study"),
    ActionSpec("play", "共同娱乐", "Play"),
    ActionSpec("drag", "拖拽/提起", "Raised"),
)


class CompanionController:
    def __init__(self, save_path: Path | None = None, auto_load: bool = True) -> None:
        self.save_path = Path(save_path) if save_path is not None else DEFAULT_SAVE_PATH
        self.character_pack = load_default_character_pack()
        loaded_state = load_state(self.save_path) if auto_load else None
        self.state = loaded_state or create_initial_state(now=0)
        self.now = 0
        self.tick_count = 0
        self.last_motion = "Default"
        self.last_feedback = "信号稳定。先从一个简单动作开始。"
        self.last_delta_text = "暂无变化"
        self.last_allowed = True
        self.last_events = self._build_events(effect="ATTENTION")
        if loaded_state is None:
            self._persist()

    def get_snapshot(self) -> dict[str, object]:
        return {
            "character_name": self.state.character_name,
            "mode": self.state.mode,
            "character_title": self.character_pack.title,
            "character_description": self.character_pack.description,
            "focus": self.state.focus,
            "charge": self.state.charge,
            "stability": self.state.stability,
            "mood": self.state.mood,
            "trust": self.state.trust,
            "exp": self.state.exp,
            "level": self.state.level,
            "coins": self.state.coins,
            "goal": describe_goal(self.state),
            "feedback": self.last_feedback,
            "motion": self.last_motion,
            "motion_caption": resolve_motion_caption(
                self.character_pack,
                motion=self.last_motion,
                mode=self.state.mode,
                allowed=self.last_allowed,
            ),
            "delta_text": self.last_delta_text,
            "allowed": self.last_allowed,
            "tick_count": self.tick_count,
            "resting": self.state.resting,
            "events": self.last_events,
            "event_preview": "\n".join(json.dumps(event, ensure_ascii=False) for event in self.last_events),
            "actions": self._build_actions(),
            "shop_items": self._build_shop_items(),
            "inventory_items": self._build_inventory_items(),
        }

    def perform_action(self, action_id: str) -> dict[str, object]:
        self.now += 5
        result = apply_action(self.state, action_id=action_id, now=self.now)
        self.state = result.state
        self.last_motion = result.motion
        self.last_feedback = result.feedback["speech"]
        self.last_delta_text = self._format_delta(result.delta)
        self.last_allowed = result.allowed
        effect = self._effect_for_action(action_id, result.allowed)
        self.last_events = self._build_events(effect=effect)
        self._persist()
        return self.get_snapshot()

    def buy_selected_item(self, item_id: str) -> dict[str, object]:
        self.state = purchase_item(self.state, item_id)
        item = BUYABLE_ITEMS[item_id]
        self.last_motion = "Shop"
        self.last_feedback = f"已购买：{item.name}。放进背包里了。"
        self.last_delta_text = f"coins -{item.price}"
        self.last_allowed = True
        self.last_events = self._build_events(effect="SWITCH")
        self._persist()
        return self.get_snapshot()

    def use_selected_item(self, item_id: str, usage: str) -> dict[str, object]:
        self.now += 5
        item = BUYABLE_ITEMS[item_id]
        try:
            self.state = use_inventory_item(self.state, item_id=item_id, usage=usage, now=self.now)
        except ValueError as exc:
            self.last_motion = "SwitchDown"
            self.last_feedback = str(exc)
            self.last_delta_text = "数值无变化"
            self.last_allowed = False
            self.last_events = self._build_events(effect="DISAPPOINTED")
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
        self.last_delta_text = self._format_item_effect(item_id, usage)
        self.last_allowed = True
        effect = "ATTENTION" if usage in {"feed", "gift"} else "SWITCH"
        self.last_events = self._build_events(effect=effect)
        self._persist()
        return self.get_snapshot()

    def advance_tick(self) -> dict[str, object]:
        self.now += TICK_SECONDS
        self.tick_count += 1
        self.state = apply_tick(self.state, ticks=1, now=self.now)
        self.last_motion = "Tick"
        self.last_feedback = "时间过去了 15 秒。她还在持续变化。"
        self.last_delta_text = "tick -15s"
        self.last_allowed = True
        self.last_events = self._build_events(effect="")
        self._persist()
        return self.get_snapshot()

    def _persist(self) -> None:
        save_state(self.state, self.save_path)

    def _build_events(self, effect: str) -> list[dict[str, str]]:
        fallback_events = build_fallback_events(
            state=self.state,
            feedback=self.last_feedback,
            choices=[entry["label"] for entry in self._build_actions()],
            effect=effect,
        )
        return validate_events(
            state=self.state,
            events=fallback_events,
            fallback_feedback=self.last_feedback,
            choices=[entry["label"] for entry in self._build_actions()],
        )

    def _build_actions(self) -> list[dict[str, object]]:
        actions: list[dict[str, object]] = []
        for spec in ACTION_SPECS:
            label = "结束休息" if spec.action_id == "rest" and self.state.resting else spec.label
            enabled = self._is_action_enabled(spec.action_id)
            actions.append(
                {
                    "action_id": spec.action_id,
                    "label": label,
                    "motion": spec.motion,
                    "enabled": enabled,
                }
            )
        return actions

    def _build_shop_items(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for item in BUYABLE_ITEMS.values():
            unlocked = self.state.level >= item.unlock_level and self.state.trust >= item.unlock_trust
            rows.append(
                {
                    "item_id": item.item_id,
                    "name": item.name,
                    "category": item.category,
                    "price": item.price,
                    "affordable": self.state.coins >= item.price,
                    "unlocked": unlocked,
                }
            )
        return rows

    def _build_inventory_items(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for item in BUYABLE_ITEMS.values():
            count = self.state.inventory[item.item_id]
            rows.append(
                {
                    "item_id": item.item_id,
                    "name": item.name,
                    "category": item.category,
                    "count": count,
                    "can_feed": item.category == "food" and count > 0,
                    "can_gift": item.category == "gift" and count > 0,
                    "can_use": item.category == "tool" and count > 0,
                }
            )
        return rows

    def _is_action_enabled(self, action_id: str) -> bool:
        if self.state.mode == "Overload" and action_id not in {"soothe", "rest"}:
            return False
        if action_id == "study" and self.state.focus < 20:
            return False
        if action_id == "play" and self.state.charge < 10:
            return False
        return True

    def _format_delta(self, delta: dict[str, float]) -> str:
        if not delta:
            return "数值无变化"
        parts: list[str] = []
        labels = {
            "focus": "focus",
            "charge": "charge",
            "stability": "stability",
            "mood": "mood",
            "trust": "trust",
            "exp": "exp",
            "coins": "coins",
        }
        for key, value in delta.items():
            sign = "+" if value > 0 else ""
            parts.append(f"{labels.get(key, key)} {sign}{value}")
        return " / ".join(parts)

    def _format_item_effect(self, item_id: str, usage: str) -> str:
        item = BUYABLE_ITEMS[item_id]
        parts: list[str] = []
        for stat_name, amount in item.effects.items():
            if usage == "gift" and stat_name not in {"mood", "trust"}:
                continue
            if usage == "feed" and stat_name not in {"charge", "mood", "stability"}:
                continue
            sign = "+" if amount > 0 else ""
            parts.append(f"{stat_name} {sign}{amount}")
        return " / ".join(parts) if parts else f"{item.name} 已使用"

    def _effect_for_action(self, action_id: str, allowed: bool) -> str:
        if not allowed:
            return "OVERLOAD" if self.state.mode == "Overload" else "DISAPPOINTED"
        effect_map = {
            "touch": "ATTENTION",
            "soothe": "SWITCH",
            "rest": "SWITCH",
            "study": "ATTENTION",
            "play": "ATTENTION",
            "drag": "SWITCH",
        }
        return effect_map.get(action_id, "")
