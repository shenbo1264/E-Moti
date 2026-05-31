from __future__ import annotations

from .engine import apply_action, create_initial_state, describe_goal, purchase_item, use_inventory_item


def _format_stats(prefix: str, state) -> str:
    return (
        f"{prefix} 模式={state.mode} "
        f"focus={state.focus} charge={state.charge} stability={state.stability} "
        f"mood={state.mood} trust={state.trust} exp={state.exp} level={state.level} coins={state.coins}"
    )


def run_demo_script() -> str:
    lines: list[str] = []
    state = create_initial_state(now=0)
    lines.append(_format_stats("初始", state))
    lines.append(describe_goal(state))

    touch = apply_action(state, action_id="touch", now=5)
    state = touch.state
    lines.append(f"轻触 -> {touch.feedback['speech']}")
    lines.append(_format_stats("轻触后", state))

    study = apply_action(state, action_id="study", now=20)
    state = study.state
    lines.append(f"共同学习 -> 获得 {study.delta['coins']} coins / {study.delta['exp']} exp")
    lines.append(_format_stats("学习后", state))

    state = purchase_item(state, "warm_milk")
    lines.append("商店购买 -> 热牛奶 入背包")
    lines.append(_format_stats("购买后", state))

    state = use_inventory_item(state, "warm_milk", usage="feed", now=35)
    lines.append("背包使用 -> 投喂热牛奶")
    lines.append(_format_stats("投喂后", state))

    return "\n".join(lines)


if __name__ == "__main__":
    print(run_demo_script())
