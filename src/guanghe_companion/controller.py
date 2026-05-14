from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import json

from .ai_expressor import ShinsekaiAIExpressor
from .character_pack import ASSETS_ROOT, load_default_character_pack, resolve_motion_caption
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

RELATIONSHIP_UNLOCK_LINES: dict[str, str] = {
    "unlock_first_nickname": "第一次主动称呼解锁了。她开始用更亲近的方式回应你。",
    "unlock_shared_ritual": "共同日常仪式解锁了。你们之间有了一段固定的小默契。",
}

PROACTIVE_COOLDOWN_SECONDS = 120


class CompanionController:
    def __init__(
        self,
        save_path: Path | None = None,
        auto_load: bool = True,
        ai_expressor: ShinsekaiAIExpressor | None = None,
    ) -> None:
        self.save_path = Path(save_path) if save_path is not None else DEFAULT_SAVE_PATH
        self.character_pack = load_default_character_pack()
        self.ai_expressor = ai_expressor or ShinsekaiAIExpressor()
        loaded_state = load_state(self.save_path) if auto_load else None
        self.state = loaded_state or create_initial_state(now=0)
        if self.state.character_id == self.character_pack.character_id:
            self.state = replace(self.state, character_name=self.character_pack.name)
        self.now = self._logical_time_from_state(self.state) if loaded_state is not None else 0
        self.tick_count = 0
        self.last_motion = "Default"
        self.last_feedback = "信号稳定。先从一个简单动作开始。"
        self.last_delta_text = "暂无变化"
        self.last_allowed = True
        self.last_item_feedback_icon: str | None = None
        self.last_proactive_feedback: dict[str, str] | None = None
        self._last_proactive_at: dict[str, int] = {}
        self.last_events = self._build_events(effect="ATTENTION")
        if loaded_state is None:
            self._persist()

    def reset_demo_state(self) -> dict[str, object]:
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
        self.last_events = self._build_events(effect="SWITCH")
        self._persist()
        return self.get_snapshot()

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
            "relationship_stage": self._relationship_stage(),
            "next_relationship_unlock": self._next_relationship_unlock(),
            "unlocks": list(self.state.unlocks),
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
            "item_feedback_icon": self.last_item_feedback_icon,
            "proactive_feedback": self.last_proactive_feedback,
            "memory_log": list(self.state.memory_log),
            "actions": self._build_actions(),
            "shop_items": self._build_shop_items(),
            "inventory_items": self._build_inventory_items(),
        }

    def perform_action(self, action_id: str) -> dict[str, object]:
        self.now += 5
        previous_unlocks = set(self.state.unlocks)
        result = apply_action(self.state, action_id=action_id, now=self.now)
        self.state = result.state
        self.last_motion = result.motion
        self.last_feedback = result.feedback["speech"]
        self.last_delta_text = self._format_delta(result.delta)
        self.last_allowed = result.allowed
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        new_unlocks = self._new_relationship_unlocks(previous_unlocks)
        unlock_feedback = self._relationship_unlock_feedback(new_unlocks)
        if unlock_feedback:
            self.last_feedback = f"{self.last_feedback} {unlock_feedback}"
        if result.allowed:
            self._remember(kind="互动", summary=f"{self._action_label(action_id)}：{self.last_feedback}", motion=result.motion)
            self._remember_relationship_unlocks(new_unlocks)
        effect = "SHOCKED" if new_unlocks else self._effect_for_action(action_id, result.allowed)
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
        self.last_item_feedback_icon = None
        self.last_proactive_feedback = None
        self.last_events = self._build_events(effect="SWITCH")
        self._persist()
        return self.get_snapshot()

    def use_selected_item(self, item_id: str, usage: str) -> dict[str, object]:
        self.now += 5
        item = BUYABLE_ITEMS[item_id]
        previous_unlocks = set(self.state.unlocks)
        try:
            self.state = use_inventory_item(self.state, item_id=item_id, usage=usage, now=self.now)
        except ValueError as exc:
            self.last_motion = "SwitchDown"
            self.last_feedback = str(exc)
            self.last_delta_text = "数值无变化"
            self.last_allowed = False
            self.last_item_feedback_icon = None
            self.last_proactive_feedback = None
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
        new_unlocks = self._new_relationship_unlocks(previous_unlocks)
        unlock_feedback = self._relationship_unlock_feedback(new_unlocks)
        if unlock_feedback:
            self.last_feedback = f"{self.last_feedback} {unlock_feedback}"
        self.last_delta_text = self._format_item_effect(item_id, usage)
        self.last_allowed = True
        self.last_item_feedback_icon = self._item_icon_path(item)
        self.last_proactive_feedback = None
        self._remember(
            kind=self._usage_memory_kind(usage),
            summary=f"{self._usage_memory_kind(usage)}了 {item.name}：{self.last_delta_text}",
            motion=self.last_motion,
            item_id=item_id,
        )
        self._remember_relationship_unlocks(new_unlocks)
        effect = "SHOCKED" if new_unlocks else "ATTENTION" if usage in {"feed", "gift"} else "SWITCH"
        self.last_events = self._build_events(effect=effect)
        self._persist()
        return self.get_snapshot()

    def advance_tick(self) -> dict[str, object]:
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
        self.last_proactive_feedback = self._select_proactive_feedback(previous_state)
        if self.last_proactive_feedback:
            self.last_feedback = self.last_proactive_feedback["speech"]
            self._last_proactive_at[self.last_proactive_feedback["kind"]] = self.now
            self._remember(
                kind="主动陪伴",
                summary=self.last_proactive_feedback["summary"],
                motion=self.last_motion,
            )
        self._remember_relationship_unlocks(new_unlocks)
        effect = "SHOCKED" if new_unlocks else "ATTENTION" if self.last_proactive_feedback else ""
        self.last_events = self._build_events(effect=effect)
        self._persist()
        return self.get_snapshot()

    def trigger_demo_proactive(self, scenario: str) -> dict[str, object]:
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
        return self.advance_tick()

    def _persist(self) -> None:
        save_state(self.state, self.save_path)

    def _logical_time_from_state(self, state: CompanionState) -> int:
        times = [state.last_interaction_at, state.last_tick_at]
        if state.last_gift_at is not None:
            times.append(state.last_gift_at)
        for entry in state.memory_log:
            at = entry.get("at")
            if isinstance(at, int):
                times.append(at)
        return max(0, *times)

    def _build_events(self, effect: str) -> list[dict[str, str]]:
        fallback_events = build_fallback_events(
            state=self.state,
            feedback=self.last_feedback,
            choices=[entry["label"] for entry in self._build_actions()],
            effect=effect,
        )
        snapshot = {
            "character_name": self.state.character_name,
            "mode": self.state.mode,
            "motion": self.last_motion,
            "focus": self.state.focus,
            "charge": self.state.charge,
            "stability": self.state.stability,
            "mood": self.state.mood,
            "trust": self.state.trust,
            "feedback": self.last_feedback,
            "delta_text": self.last_delta_text,
            "goal": describe_goal(self.state),
            "actions": self._build_actions(),
        }
        expressed_events = self.ai_expressor.express(snapshot, effect=effect)
        return validate_events(
            state=self.state,
            events=expressed_events or fallback_events,
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
                    "icon_path": self._item_icon_path(item),
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
                    "icon_path": self._item_icon_path(item),
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

    def _item_icon_path(self, item) -> str:
        if not item.icon:
            return ""
        return str(ASSETS_ROOT / self.character_pack.character_id / item.icon)

    def _remember(self, kind: str, summary: str, motion: str, item_id: str | None = None) -> None:
        entry: dict[str, object] = {
            "at": self.now,
            "kind": kind,
            "summary": summary,
            "motion": motion,
        }
        if item_id is not None:
            entry["item_id"] = item_id
        self.state.memory_log.insert(0, entry)
        del self.state.memory_log[12:]

    def _action_label(self, action_id: str) -> str:
        for spec in ACTION_SPECS:
            if spec.action_id == action_id:
                return spec.label
        return action_id

    def _usage_memory_kind(self, usage: str) -> str:
        if usage == "feed":
            return "投喂"
        if usage == "gift":
            return "赠礼"
        return "使用"

    def _relationship_stage(self) -> str:
        if self.state.trust >= 35:
            return "共同日常"
        if self.state.trust >= 20:
            return "熟悉的陪伴"
        return "初识"

    def _next_relationship_unlock(self) -> str:
        if "unlock_first_nickname" not in self.state.unlocks:
            return "信任达到 20：解锁第一次主动称呼"
        if "unlock_shared_ritual" not in self.state.unlocks:
            return "信任达到 35：解锁共同日常仪式"
        return "继续保持稳定陪伴，观察她的主动回应"

    def _new_relationship_unlocks(self, previous_unlocks: set[str]) -> list[str]:
        return [unlock_id for unlock_id in self.state.unlocks if unlock_id not in previous_unlocks]

    def _relationship_unlock_feedback(self, unlocks: list[str]) -> str:
        return " ".join(RELATIONSHIP_UNLOCK_LINES[unlock_id] for unlock_id in unlocks if unlock_id in RELATIONSHIP_UNLOCK_LINES)

    def _remember_relationship_unlocks(self, unlocks: list[str]) -> None:
        for unlock_id in unlocks:
            line = RELATIONSHIP_UNLOCK_LINES.get(unlock_id)
            if line:
                self._remember(kind="关系解锁", summary=line, motion=self.last_motion)

    def _select_proactive_feedback(self, previous_state: CompanionState) -> dict[str, str] | None:
        idle_seconds = self.now - self.state.last_interaction_at
        if self.state.charge < 25 and self._can_emit_proactive("low_charge"):
            line = self._proactive_line("low_charge")
            return {
                "kind": "low_charge",
                "speech": line,
                "summary": f"能量有点低时主动陪伴：{line}",
            }
        if (
            idle_seconds > 60
            and self.state.mood <= 35
            and self.state.mood < previous_state.mood
            and self._can_emit_proactive("low_mood")
        ):
            line = self._proactive_line("low_mood")
            return {
                "kind": "low_mood",
                "speech": line,
                "summary": f"久未互动后主动陪伴：{line}",
            }
        return None

    def _can_emit_proactive(self, kind: str) -> bool:
        last_at = self._last_proactive_at.get(kind)
        return last_at is None or self.now - last_at >= PROACTIVE_COOLDOWN_SECONDS

    def _proactive_line(self, kind: str) -> str:
        has_ritual = "unlock_shared_ritual" in self.state.unlocks
        has_nickname = "unlock_first_nickname" in self.state.unlocks
        if kind == "low_charge":
            if has_ritual:
                return "像我们的小仪式一样，先把节奏放轻一点吧。我的能量有点低，陪你安静待一会儿也很好。"
            if has_nickname:
                return "现在可以更亲近一点叫你了。能量有点低，我想挨着你慢慢缓一会儿。"
            return "能量有点低了。我会把亮度放轻一点；你想休息或给我一点小点心都可以。"
        if has_ritual:
            return "刚才安静得有点久，我还在这里。按我们的小默契，我先轻轻靠近你。"
        if has_nickname:
            return "刚才安静得有点久，我还在这里。现在我可以更自然地靠近你一点。"
        return "刚才安静得有点久，我还在这里。你不用立刻回应，我只是想靠近一点。"

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
