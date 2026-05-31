from __future__ import annotations

import json

from .character_pack import ASSETS_ROOT, DEFAULT_CHARACTER_ID
from .models import ItemDefinition


def load_default_shop_items() -> dict[str, ItemDefinition]:
    return load_shop_items(DEFAULT_CHARACTER_ID)


def load_shop_items(character_id: str) -> dict[str, ItemDefinition]:
    payload = json.loads((ASSETS_ROOT / character_id / "shop_items.json").read_text(encoding="utf-8"))
    items: dict[str, ItemDefinition] = {}
    for row in payload:
        item = ItemDefinition(
            item_id=row["item_id"],
            name=row["name"],
            category=row["category"],
            price=int(row["price"]),
            effects={key: float(value) for key, value in row["effects"].items()},
            icon=str(row.get("icon", "")),
            unlock_level=int(row.get("unlock_level", 1)),
            unlock_trust=float(row.get("unlock_trust", 0)),
        )
        items[item.item_id] = item
    return items
