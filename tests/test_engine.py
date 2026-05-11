from guanghe_companion.engine import (
    BUYABLE_ITEMS,
    apply_action,
    apply_tick,
    create_initial_state,
    purchase_item,
    use_inventory_item,
)


def test_touch_action_updates_stats_and_feedback():
    state = create_initial_state(now=0)

    result = apply_action(state, action_id="touch", now=5)

    assert result.allowed is True
    assert result.motion == "TouchHead"
    assert result.state.focus == 70
    assert result.state.mood == 62
    assert result.state.trust == 6
    assert result.state.mode == "Calm"
    assert result.feedback["character_name"] == "光核伴生体"
    assert "记录下来了" in result.feedback["speech"]
    assert result.delta["focus"] == -2
    assert result.delta["mood"] == 4
    assert result.delta["trust"] == 1


def test_tick_applies_decay_and_rest_recovery():
    state = create_initial_state(now=0)
    resting = apply_action(state, action_id="rest", now=5).state

    after_tick = apply_tick(resting, ticks=1, now=20)

    assert after_tick.resting is True
    assert after_tick.charge == 63.7
    assert after_tick.focus == 74.5
    assert after_tick.stability == 80
    assert after_tick.mode == "Calm"


def test_study_rewards_exp_and_coins():
    state = create_initial_state(now=0)

    result = apply_action(state, action_id="study", now=15)

    assert result.allowed is True
    assert result.motion == "Study"
    assert result.state.focus == 60
    assert result.state.charge == 60
    assert result.state.trust == 9
    assert result.state.exp == 8
    assert result.state.coins == 28
    assert result.state.level == 1
    assert result.delta["coins"] == 8


def test_purchase_and_use_food_closes_coin_inventory_loop():
    state = create_initial_state(now=0)
    state = apply_action(state, action_id="study", now=15).state

    purchased = purchase_item(state, item_id="warm_milk")

    assert purchased.coins == 16
    assert purchased.inventory["warm_milk"] == 1

    used = use_inventory_item(purchased, item_id="warm_milk", usage="feed", now=30)

    assert used.focus == 60
    assert used.charge == 72
    assert used.mood == 60
    assert used.inventory["warm_milk"] == 0


def test_feed_refuses_when_charge_is_already_full_and_keeps_item():
    state = create_initial_state(now=0)
    state.coins = 120
    state.charge = 96
    state = purchase_item(state, item_id="warm_milk")

    try:
        use_inventory_item(state, item_id="warm_milk", usage="feed", now=30)
    except ValueError as exc:
        assert "能量已经很满" in str(exc)
    else:
        raise AssertionError("feeding should be refused when charge is already full")

    assert state.inventory["warm_milk"] == 1
    assert state.charge == 96


def test_gift_increases_trust_and_unlocks_first_goal():
    state = create_initial_state(now=0)
    state.coins = 120

    for item_id in ["star_hairpin", "star_hairpin", "comet_ribbon", "memory_shell"]:
        state = purchase_item(state, item_id=item_id)
        state = use_inventory_item(state, item_id=item_id, usage="gift", now=state.last_interaction_at + 10)

    assert state.trust >= 20
    assert "unlock_first_nickname" in state.unlocks
    assert state.current_goal_id == "reach_trust_35"


def test_overload_blocks_study_with_fallback_feedback():
    state = create_initial_state(now=0)
    state.stability = 20
    state.mode = "Overload"

    result = apply_action(state, action_id="study", now=10)

    assert result.allowed is False
    assert result.motion == "SwitchDown"
    assert result.state.stability == 20
    assert result.state.exp == 0
    assert "先让我缓一缓" in result.feedback["speech"]


def test_low_focus_still_returns_blocked_feedback_instead_of_throwing():
    state = create_initial_state(now=0)
    state.focus = 10

    result = apply_action(state, action_id="study", now=10)

    assert result.allowed is False
    assert result.motion == "SwitchDown"
    assert result.state.exp == 0
    assert "先让我休息一下" in result.feedback["speech"]


def test_shop_catalog_contains_expected_mvp_items():
    assert len(BUYABLE_ITEMS) == 8
    assert BUYABLE_ITEMS["warm_milk"].price == 12
    assert BUYABLE_ITEMS["star_hairpin"].category == "gift"
