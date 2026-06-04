from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import guanghe_companion.character_pack as character_pack_module
from .character_pack import DEFAULT_CHARACTER_ID, CharacterPack, load_character_pack, load_character_pack_from_dir
from .models import ItemDefinition
from .shop_items import load_shop_items, load_shop_items_from_dir


@dataclass(frozen=True, slots=True)
class CharacterResources:
    character_pack: CharacterPack
    shop_items: dict[str, ItemDefinition]
    asset_dir: Path


def load_character_resources(character_id: str = DEFAULT_CHARACTER_ID) -> CharacterResources:
    return CharacterResources(
        character_pack=load_character_pack(character_id),
        shop_items=load_shop_items(character_id),
        asset_dir=character_pack_module.ASSETS_ROOT / character_id,
    )


def load_character_resources_from_dir(asset_dir: Path | str) -> CharacterResources:
    root = Path(asset_dir)
    return CharacterResources(
        character_pack=load_character_pack_from_dir(root),
        shop_items=load_shop_items_from_dir(root),
        asset_dir=root,
    )
