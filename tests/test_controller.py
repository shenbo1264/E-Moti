from guanghe_companion.controller import CompanionController


def test_snapshot_exposes_status_actions_shop_and_inventory():
    controller = CompanionController(auto_load=False)

    snapshot = controller.get_snapshot()

    assert snapshot["character_name"] == "光核伴生体"
    assert snapshot["mode"] == "Calm"
    assert snapshot["coins"] == 20
    assert len(snapshot["actions"]) == 6
    assert snapshot["actions"][0]["label"] == "轻触"
    assert len(snapshot["shop_items"]) == 8
    assert snapshot["shop_items"][0]["item_id"] == "warm_milk"
    assert snapshot["inventory_items"][0]["count"] == 0
    assert len(snapshot["events"]) == 3
    assert snapshot["events"][0]["character_name"] == "光核伴生体"


def test_controller_closes_buy_and_use_loop():
    controller = CompanionController(auto_load=False)

    study = controller.perform_action("study")
    assert study["coins"] == 28
    assert "共同学习" in study["feedback"]

    purchased = controller.buy_selected_item("warm_milk")
    assert purchased["coins"] == 16
    warm_milk = next(item for item in purchased["inventory_items"] if item["item_id"] == "warm_milk")
    assert warm_milk["count"] == 1

    fed = controller.use_selected_item("warm_milk", usage="feed")
    assert fed["charge"] == 72
    assert fed["mood"] == 60
    assert "投喂" in fed["feedback"]


def test_controller_reports_refused_feed_without_consuming_item():
    controller = CompanionController(auto_load=False)
    controller.state.coins = 120
    controller.state.charge = 96
    controller.buy_selected_item("warm_milk")

    snapshot = controller.use_selected_item("warm_milk", usage="feed")
    warm_milk = next(item for item in snapshot["inventory_items"] if item["item_id"] == "warm_milk")

    assert snapshot["allowed"] is False
    assert snapshot["motion"] == "SwitchDown"
    assert "能量已经很满" in snapshot["feedback"]
    assert warm_milk["count"] == 1
    assert snapshot["charge"] == 96


def test_controller_reports_blocked_action_without_crashing():
    controller = CompanionController(auto_load=False)
    controller.state.focus = 10

    snapshot = controller.perform_action("study")

    assert snapshot["allowed"] is False
    assert snapshot["motion"] == "SwitchDown"
    assert "先让我休息一下" in snapshot["feedback"]
    assert snapshot["events"][0]["effect"] == "DISAPPOINTED"


def test_controller_tick_updates_status_and_tick_counter():
    controller = CompanionController(auto_load=False)
    initial_focus = controller.get_snapshot()["focus"]

    snapshot = controller.advance_tick()

    assert snapshot["focus"] == initial_focus - 0.5
    assert snapshot["tick_count"] == 1
