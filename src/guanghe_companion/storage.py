from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import fields
from pathlib import Path

from .engine import create_initial_state
from .models import CompanionState
from .runtime_paths import default_save_path, demo_save_path
from .shop_items import load_default_shop_items

DEFAULT_SAVE_PATH = default_save_path()
DEMO_SAVE_PATH = demo_save_path()
CURRENT_SAVE_SCHEMA_VERSION = 1


def save_state(state: CompanionState, path: Path | str = DEFAULT_SAVE_PATH) -> None:
    SaveManager(path).save(state)


def load_state(
    path: Path | str = DEFAULT_SAVE_PATH,
    *,
    expected_character_id: str | None = None,
) -> CompanionState | None:
    return SaveManager(path, expected_character_id=expected_character_id).load()


@dataclass(frozen=True, slots=True)
class SaveManager:
    path: Path | str = DEFAULT_SAVE_PATH
    inventory_item_ids: Iterable[str] | None = None
    expected_character_id: str | None = None

    def save(self, state: CompanionState) -> None:
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(state)
        payload["schema_version"] = CURRENT_SAVE_SCHEMA_VERSION
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> CompanionState | None:
        target = Path(self.path)
        if not target.exists():
            return None
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        try:
            migrated = _migrate_payload(payload, item_ids=self.inventory_item_ids)
            if (
                self.expected_character_id is not None
                and migrated.get("character_id") != self.expected_character_id
            ):
                return None
            return CompanionState(**migrated)
        except (TypeError, ValueError):
            return None


def _migrate_payload(
    payload: dict[str, object],
    *,
    item_ids: Iterable[str] | None = None,
) -> dict[str, object]:
    defaults = asdict(create_initial_state(now=0))
    state_fields = {field.name for field in fields(CompanionState)}
    migrated = {
        field_name: payload.get(field_name, defaults[field_name])
        for field_name in state_fields
        if field_name in defaults
    }
    migrated["schema_version"] = _normalize_schema_version(payload.get("schema_version"))
    migrated["memory_log"] = _normalize_memory_log(payload.get("memory_log"))
    migrated["inventory"] = _normalize_inventory(payload.get("inventory"), item_ids=item_ids)
    return migrated


def _normalize_schema_version(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return CURRENT_SAVE_SCHEMA_VERSION
    if value != CURRENT_SAVE_SCHEMA_VERSION:
        return CURRENT_SAVE_SCHEMA_VERSION
    return value


def _normalize_memory_log(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(entry) for entry in value if isinstance(entry, dict)]


def _normalize_inventory(value: object, *, item_ids: Iterable[str] | None = None) -> dict[str, int]:
    inventory_keys = tuple(item_ids) if item_ids is not None else tuple(load_default_shop_items())
    inventory = {item_id: 0 for item_id in inventory_keys}
    if not isinstance(value, dict):
        return inventory
    for item_id in inventory:
        inventory[item_id] = _normalize_inventory_count(value.get(item_id))
    return inventory


def _normalize_inventory_count(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, count)


def logical_time_from_state(state: CompanionState) -> int:
    times = [state.last_interaction_at, state.last_tick_at]
    if state.last_gift_at is not None:
        times.append(state.last_gift_at)
    for entry in state.memory_log:
        at = entry.get("at")
        if isinstance(at, int):
            times.append(at)
    return max(0, *times)
