from guanghe_companion.engine import create_initial_state
from guanghe_companion.inventory import (
    InventoryService,
    InventoryUseRequest,
    ShopPurchaseRequest,
    ShopService,
    format_item_effect,
)


def icon_path(item):
    return f"icons/{item.item_id}.png"


def test_shop_service_builds_typed_rows_and_legacy_shape():
    state = create_initial_state(now=0)

    rows = ShopService(state, icon_path).shop_items()

    assert rows[0].item_id == "warm_milk"
    assert rows[0].name == "热牛奶"
    assert rows[0].icon_path == "icons/warm_milk.png"
    assert rows[0].affordable is True
    assert rows[0].unlocked is True
    assert rows[0].to_legacy_dict() == {
        "item_id": "warm_milk",
        "name": "热牛奶",
        "category": "food",
        "icon_path": "icons/warm_milk.png",
        "price": 12,
        "affordable": True,
        "unlocked": True,
    }


def test_inventory_service_builds_typed_rows_and_uses_request():
    state = create_initial_state(now=0)
    state.inventory["warm_milk"] = 1

    service = InventoryService(state, icon_path)
    rows = service.inventory_items()
    next_state = service.use(InventoryUseRequest(item_id="warm_milk", usage="feed"), now=5)

    assert rows[0].item_id == "warm_milk"
    assert rows[0].count == 1
    assert rows[0].can_feed is True
    assert rows[0].to_legacy_dict()["icon_path"] == "icons/warm_milk.png"
    assert next_state.inventory["warm_milk"] == 0
    assert next_state.charge == 77


def test_shop_purchase_request_updates_state_without_ui_dicts():
    state = create_initial_state(now=0)

    next_state = ShopService(state, icon_path).purchase(ShopPurchaseRequest(item_id="warm_milk"))

    assert next_state.coins == 8
    assert next_state.inventory["warm_milk"] == 1


def test_format_item_effect_keeps_usage_specific_stats():
    assert format_item_effect("warm_milk", "feed") == "charge +12.0 / mood +2.0"
    assert format_item_effect("energy_candy", "feed") == "charge +20.0 / stability -2.0"
    assert format_item_effect("star_hairpin", "gift") == "mood +8.0 / trust +3.0"
    assert format_item_effect("learning_sticker", "use") == "study_bonus_exp +4.0"
