from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from .models import ActionResult, CompanionState, ItemDefinition
from .shop_items import load_default_shop_items

STAT_MIN = 0.0
STAT_MAX = 100.0
TICK_SECONDS = 15
CHARACTER_NAME = "星汐"


BUYABLE_ITEMS: dict[str, ItemDefinition] = load_default_shop_items()


def create_initial_state(now: int = 0) -> CompanionState:
    return _finalize_state(
        CompanionState(
            character_id="original_oc",
            character_name=CHARACTER_NAME,
            focus=72,
            charge=65,
            stability=78,
            mood=58,
            trust=5,
            exp=0,
            level=1,
            coins=20,
            mode="Calm",
            resting=False,
            inventory={item_id: 0 for item_id in BUYABLE_ITEMS},
            unlocks=[],
            current_goal_id="reach_trust_20",
            last_interaction_at=now,
            last_tick_at=now,
        )
    )


def apply_action(state: CompanionState, action_id: str, now: int) -> ActionResult:
    normalized = _finalize_state(state)
    if normalized.mode == "Overload" and action_id not in {"soothe", "rest"}:
        return _blocked_result(normalized, action_id, "先让我缓一缓。现在做这个会把频率压坏。")

    handlers = {
        "touch": _apply_touch,
        "soothe": _apply_soothe,
        "rest": _apply_rest,
        "study": _apply_study,
        "play": _apply_play,
        "drag": _apply_drag,
    }
    if action_id not in handlers:
        raise ValueError(f"Unknown action: {action_id}")

    try:
        next_state, motion, delta, line = handlers[action_id](normalized, now)
    except ValueError as exc:
        return _blocked_result(normalized, action_id, str(exc))

    finalized = _finalize_state(next_state)
    return ActionResult(
        state=finalized,
        motion=motion,
        allowed=True,
        delta=delta,
        feedback=_feedback_payload(finalized.character_name, line),
    )


def apply_tick(state: CompanionState, ticks: int, now: int) -> CompanionState:
    next_state = deepcopy(state)
    for _ in range(ticks):
        next_state.charge -= 1
        next_state.focus -= 0.5
        if now - next_state.last_interaction_at > 60:
            next_state.mood -= 1
        if next_state.mood >= 75:
            next_state.trust += 0.2
        if next_state.charge < 20 or next_state.focus < 15:
            next_state.stability -= 1
        if next_state.resting:
            next_state.focus += 3
            next_state.stability += 2
            next_state.charge -= 0.3
    next_state.last_tick_at = now
    return _finalize_state(next_state)


def purchase_item(state: CompanionState, item_id: str) -> CompanionState:
    item = BUYABLE_ITEMS[item_id]
    if state.coins < item.price:
        raise ValueError("Not enough coins.")
    if state.level < item.unlock_level or state.trust < item.unlock_trust:
        raise ValueError("Item is locked.")

    next_state = deepcopy(state)
    next_state.coins -= item.price
    next_state.inventory[item_id] += 1
    return _finalize_state(next_state)


def use_inventory_item(state: CompanionState, item_id: str, usage: str, now: int) -> CompanionState:
    item = BUYABLE_ITEMS[item_id]
    if state.inventory.get(item_id, 0) <= 0:
        raise ValueError("Item is not in inventory.")
    if item.category == "food" and usage == "feed" and state.charge >= 95:
        raise ValueError("能量已经很满了。先不用继续投喂。")

    next_state = deepcopy(state)

    if item.category == "food" and usage == "feed":
        next_state.inventory[item_id] -= 1
        for stat_name, amount in item.effects.items():
            setattr(next_state, stat_name, getattr(next_state, stat_name) + amount)
        next_state.last_interaction_at = now
    elif item.category == "gift" and usage == "gift":
        next_state.inventory[item_id] -= 1
        scale = _gift_scale(next_state, item_id, now)
        for stat_name, amount in item.effects.items():
            setattr(next_state, stat_name, getattr(next_state, stat_name) + amount * scale)
        next_state.last_gift_item_id = item_id
        next_state.last_gift_at = now
        next_state.same_gift_chain = next_state.same_gift_chain + 1 if scale < 1 else 1
        next_state.last_interaction_at = now
    elif item.category == "tool":
        next_state.inventory[item_id] -= 1
        if "study_bonus_exp" in item.effects:
            next_state.study_bonus_exp += int(item.effects["study_bonus_exp"])
        else:
            for stat_name, amount in item.effects.items():
                setattr(next_state, stat_name, getattr(next_state, stat_name) + amount)
        next_state.last_interaction_at = now
    else:
        raise ValueError("Invalid usage for item.")

    return _finalize_state(next_state)


def describe_goal(state: CompanionState) -> str:
    goal_map = {
        "reach_trust_20": "目标：让信任达到 20，解锁第一次主动称呼。",
        "reach_trust_35": "目标：让信任达到 35，解锁共同日常仪式。",
        "maintain_glow": "目标：连续保持 Glow，证明她会稳定回应你。",
    }
    return goal_map[state.current_goal_id]


def _apply_touch(state: CompanionState, now: int) -> tuple[CompanionState, str, dict[str, float], str]:
    next_state = deepcopy(state)
    next_state.focus -= 2
    next_state.mood += 4
    next_state.trust += 1
    next_state.resting = False
    next_state.last_interaction_at = now
    return next_state, "TouchHead", {"focus": -2, "mood": 4, "trust": 1}, "我记录下来了。这不是指令，是你靠近我的方式。"


def _apply_soothe(state: CompanionState, now: int) -> tuple[CompanionState, str, dict[str, float], str]:
    next_state = deepcopy(state)
    next_state.stability += 10
    next_state.mood += 4
    next_state.focus -= 2
    next_state.resting = False
    next_state.last_interaction_at = now
    return next_state, "Comfort", {"stability": 10, "mood": 4, "focus": -2}, "先把杂音压低一点。我能重新站稳。"


def _apply_rest(state: CompanionState, now: int) -> tuple[CompanionState, str, dict[str, float], str]:
    next_state = deepcopy(state)
    next_state.resting = not state.resting
    next_state.last_interaction_at = now
    line = "我先把频率调低一点。你在的话，我就放心休息。" if next_state.resting else "我醒了。可以继续一起行动。"
    return next_state, "Sleep", {}, line


def _apply_study(state: CompanionState, now: int) -> tuple[CompanionState, str, dict[str, float], str]:
    if state.focus < 20:
        raise ValueError("现在不行。我会把注意力弄碎的。先让我休息一下。")

    next_state = deepcopy(state)
    exp_gain = 8 + next_state.study_bonus_exp
    next_state.focus -= 12
    next_state.charge -= 5
    next_state.trust += 4
    next_state.exp += exp_gain
    next_state.coins += 8
    next_state.study_bonus_exp = 0
    next_state.resting = False
    next_state.last_interaction_at = now
    delta = {"focus": -12, "charge": -5, "trust": 4, "exp": exp_gain, "coins": 8}
    return next_state, "Study", delta, "把这一小段时间记成共同学习吧。你在，我就更稳。"


def _apply_play(state: CompanionState, now: int) -> tuple[CompanionState, str, dict[str, float], str]:
    if state.charge < 10:
        raise ValueError("现在再闹下去，我会直接掉线。先补一点能量。")

    next_state = deepcopy(state)
    next_state.focus -= 6
    next_state.charge -= 4
    next_state.mood += 12
    next_state.trust += 2
    next_state.coins += 3
    next_state.resting = False
    next_state.last_interaction_at = now
    delta = {"focus": -6, "charge": -4, "mood": 12, "trust": 2, "coins": 3}
    return next_state, "Play", delta, "这一下很有效。我开始想把今天过得更亮一点。"


def _apply_drag(state: CompanionState, now: int) -> tuple[CompanionState, str, dict[str, float], str]:
    next_state = deepcopy(state)
    if state.mode in {"Glow", "Calm"}:
        next_state.mood += 2
        next_state.trust += 1
        delta = {"mood": 2, "trust": 1}
        line = "慢一点提起我就好。我知道你没有在赶我。"
    else:
        next_state.mood -= 2
        delta = {"mood": -2}
        line = "现在别拎我。我会更乱。"
    next_state.resting = False
    next_state.last_interaction_at = now
    return next_state, "Raised", delta, line


def _blocked_result(state: CompanionState, action_id: str, line: str) -> ActionResult:
    motion_map = {
        "touch": "SwitchDown",
        "study": "SwitchDown",
        "play": "SwitchDown",
        "drag": "SwitchDown",
    }
    return ActionResult(
        state=_finalize_state(state),
        motion=motion_map.get(action_id, "SwitchDown"),
        allowed=False,
        delta={},
        feedback=_feedback_payload(state.character_name, line),
    )


def _gift_scale(state: CompanionState, item_id: str, now: int) -> float:
    if state.last_gift_item_id == item_id and state.last_gift_at is not None and now - state.last_gift_at <= 120:
        return 0.5
    return 1.0


def _feedback_payload(character_name: str, speech: str) -> dict[str, str]:
    return {
        "character_name": character_name,
        "speech": speech,
        "sprite": "1",
        "effect": "",
    }


def _finalize_state(state: CompanionState) -> CompanionState:
    next_state = deepcopy(state)
    for field_name in ("focus", "charge", "stability", "mood", "trust"):
        setattr(next_state, field_name, _clamp(getattr(next_state, field_name)))
    next_state.level = 1 + next_state.exp // 20
    next_state.mode = _resolve_mode(next_state)
    next_state = _update_goals(next_state)
    return next_state


def _update_goals(state: CompanionState) -> CompanionState:
    next_state = deepcopy(state)
    if "unlock_first_nickname" not in next_state.unlocks and next_state.trust >= 20:
        next_state.unlocks.append("unlock_first_nickname")
        next_state.current_goal_id = "reach_trust_35"
    elif "unlock_shared_ritual" not in next_state.unlocks and next_state.trust >= 35:
        next_state.unlocks.append("unlock_shared_ritual")
        next_state.current_goal_id = "maintain_glow"
    return next_state


def _resolve_mode(state: CompanionState) -> str:
    if state.stability < 25:
        return "Overload"
    if state.mood < 35 or state.charge < 25 or state.focus < 20:
        return "Frayed"
    if state.mood >= 75 and state.stability >= 70:
        return "Glow"
    return "Calm"


def _clamp(value: float) -> float:
    clamped = max(STAT_MIN, min(STAT_MAX, value))
    return round(clamped, 1)
