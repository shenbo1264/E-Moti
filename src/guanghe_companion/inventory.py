from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .engine import BUYABLE_ITEMS, purchase_item, use_inventory_item
from .models import CompanionState, ItemDefinition

InventoryUsage = Literal["feed", "gift", "use"]
ItemIconResolver = Callable[[ItemDefinition], str]


def format_item_effect(item_id: str, usage: InventoryUsage) -> str:
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


@dataclass(frozen=True, slots=True)
class ShopPurchaseRequest:
    item_id: str


@dataclass(frozen=True, slots=True)
class InventoryUseRequest:
    item_id: str
    usage: InventoryUsage


@dataclass(frozen=True, slots=True)
class ShopItemRow:
    item_id: str
    name: str
    category: str
    icon_path: str
    price: int
    affordable: bool
    unlocked: bool

    def to_legacy_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "category": self.category,
            "icon_path": self.icon_path,
            "price": self.price,
            "affordable": self.affordable,
            "unlocked": self.unlocked,
        }


@dataclass(frozen=True, slots=True)
class InventoryItemRow:
    item_id: str
    name: str
    category: str
    icon_path: str
    count: int
    can_feed: bool
    can_gift: bool
    can_use: bool

    def to_legacy_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "category": self.category,
            "icon_path": self.icon_path,
            "count": self.count,
            "can_feed": self.can_feed,
            "can_gift": self.can_gift,
            "can_use": self.can_use,
        }


class ShopService:
    def __init__(self, state: CompanionState, item_icon_path: ItemIconResolver) -> None:
        self.state = state
        self.item_icon_path = item_icon_path

    def shop_items(self) -> list[ShopItemRow]:
        rows: list[ShopItemRow] = []
        for item in BUYABLE_ITEMS.values():
            unlocked = self.state.level >= item.unlock_level and self.state.trust >= item.unlock_trust
            rows.append(
                ShopItemRow(
                    item_id=item.item_id,
                    name=item.name,
                    category=item.category,
                    icon_path=self.item_icon_path(item),
                    price=item.price,
                    affordable=self.state.coins >= item.price,
                    unlocked=unlocked,
                )
            )
        return rows

    def purchase(self, request: ShopPurchaseRequest) -> CompanionState:
        return purchase_item(self.state, request.item_id)


class InventoryService:
    def __init__(self, state: CompanionState, item_icon_path: ItemIconResolver) -> None:
        self.state = state
        self.item_icon_path = item_icon_path

    def inventory_items(self) -> list[InventoryItemRow]:
        rows: list[InventoryItemRow] = []
        for item in BUYABLE_ITEMS.values():
            count = self.state.inventory[item.item_id]
            rows.append(
                InventoryItemRow(
                    item_id=item.item_id,
                    name=item.name,
                    category=item.category,
                    icon_path=self.item_icon_path(item),
                    count=count,
                    can_feed=item.category == "food" and count > 0,
                    can_gift=item.category == "gift" and count > 0,
                    can_use=item.category == "tool" and count > 0,
                )
            )
        return rows

    def use(self, request: InventoryUseRequest, now: int) -> CompanionState:
        return use_inventory_item(self.state, item_id=request.item_id, usage=request.usage, now=now)
