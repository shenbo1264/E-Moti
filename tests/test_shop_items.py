from pathlib import Path

from guanghe_companion.character_pack import ASSETS_ROOT
from guanghe_companion.shop_items import load_shop_items


def test_original_oc_shop_items_load_from_character_pack_config():
    items = load_shop_items("original_oc")

    assert len(items) == 8
    assert items["warm_milk"].name == "热牛奶"
    assert items["warm_milk"].price == 12
    assert items["warm_milk"].icon == "item_icons/warm_milk.png"
    assert items["star_hairpin"].category == "gift"
    assert items["learning_sticker"].effects["study_bonus_exp"] == 4

    for item in items.values():
        assert item.icon.startswith("item_icons/")
        assert Path(ASSETS_ROOT / "original_oc" / item.icon).is_file()
