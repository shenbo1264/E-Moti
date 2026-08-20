from __future__ import annotations

"""Conservative migration from E-Moti's older keyed-memory JSON shapes."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping

from .emotional_memory_service import EmotionalMemoryService


ALLOWED_LEGACY_CATEGORIES = frozenset(
    {
        "relationship_unlock",
        "relationship",
        "player_preference",
        "preference",
        "boundary",
        "shared_ritual",
        "player_alias",
        "explicit_user_memory",
    }
)
ALLOWED_KEY_PREFIXES = (
    "relationship:",
    "preference:",
    "boundary:",
    "ritual:",
    "player_alias",
    "user_memory:",
)


@dataclass(frozen=True, slots=True)
class LegacyMigrationReport:
    migrated_ids: tuple[str, ...]
    skipped_keys: tuple[str, ...]


def migrate_legacy_entries(
    service: EmotionalMemoryService,
    entries: Iterable[Mapping[str, object]],
    *,
    now: int,
) -> LegacyMigrationReport:
    migrated: list[str] = []
    skipped: list[str] = []
    for row in entries:
        key = _text(row.get("key"), 80)
        summary = _text(row.get("summary"), 240)
        category = _text(row.get("category"), 40)
        source = _text(row.get("source"), 40) or "legacy_local_memory"
        if not key or not summary or not _is_relationship_memory(key, category):
            if key:
                skipped.append(key)
            continue
        occurred_at = _timestamp(row.get("updated_at"), fallback=now)
        kind, tags = _kind_and_tags(key, category)
        memory = service.remember(
            kind=kind,
            title=_legacy_title(kind, summary),
            summary=summary,
            source=source,
            now=occurred_at,
            importance=0.78,
            tags=tags,
            pinned=kind in {"关系里程碑", "玩家希望被记住", "边界"},
            user_confirmed=True,
            metadata={"legacy_key": key, "legacy_category": category},
        )
        migrated.append(memory.memory_id)
    return LegacyMigrationReport(tuple(migrated), tuple(skipped))


def _is_relationship_memory(key: str, category: str) -> bool:
    return category in ALLOWED_LEGACY_CATEGORIES or key.startswith(ALLOWED_KEY_PREFIXES)


def _kind_and_tags(key: str, category: str) -> tuple[str, tuple[str, ...]]:
    combined = f"{key} {category}".lower()
    if "boundary" in combined:
        return "边界", ("关于你", "边界", "用户确认")
    if "preference" in combined:
        return "玩家希望被记住", ("关于你", "偏好", "用户确认")
    if "ritual" in combined:
        return "共同仪式", ("小默契", "共同日常")
    if "alias" in combined:
        return "玩家希望被记住", ("关于你", "称呼", "用户确认")
    return "关系里程碑", ("关系", "共同日常")


def _legacy_title(kind: str, summary: str) -> str:
    if kind == "边界":
        return "她认真记下的一条边界"
    if kind == "共同仪式":
        return "你们慢慢形成的小默契"
    if kind == "玩家希望被记住":
        return "你亲口交给她的一件事"
    return summary[:28]


def _text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())[:limit]


def _timestamp(value: object, *, fallback: int) -> int:
    if isinstance(value, bool):
        return max(0, int(fallback))
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return max(0, int(text))
        try:
            return max(0, int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp()))
        except ValueError:
            pass
    return max(0, int(fallback))
