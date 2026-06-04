from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CURRENT_LONG_TERM_MEMORY_SCHEMA_VERSION = 1
MAX_LONG_TERM_MEMORY_ENTRIES = 50
MAX_LONG_TERM_MEMORY_SUMMARIES = 5
MAX_LONG_TERM_MEMORY_KEY_LENGTH = 80
MAX_LONG_TERM_MEMORY_CATEGORY_LENGTH = 40
MAX_LONG_TERM_MEMORY_SUMMARY_LENGTH = 160
MAX_LONG_TERM_MEMORY_SOURCE_LENGTH = 40


def memory_kind_for_inventory_usage(usage: str) -> str:
    if usage == "feed":
        return "投喂"
    if usage == "gift":
        return "赠礼"
    return "使用"


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    at: int
    kind: str
    summary: str
    motion: str
    item_id: str | None = None

    def to_legacy_dict(self) -> dict[str, object]:
        row: dict[str, object] = {
            "at": self.at,
            "kind": self.kind,
            "summary": self.summary,
            "motion": self.motion,
        }
        if self.item_id is not None:
            row["item_id"] = self.item_id
        return row


class MemoryLogService:
    def __init__(self, memory_log: list[dict[str, object]], max_entries: int = 12) -> None:
        self.memory_log = memory_log
        self.max_entries = max_entries

    def append(self, at: int, kind: str, summary: str, motion: str, item_id: str | None = None) -> None:
        entry = MemoryEntry(at=at, kind=kind, summary=summary, motion=motion, item_id=item_id)
        self.memory_log.insert(0, entry.to_legacy_dict())
        del self.memory_log[self.max_entries :]

    def append_drafts(self, at: int, drafts: list[dict[str, object]]) -> None:
        for draft in drafts:
            self.append(
                at=at,
                kind=str(draft["kind"]),
                summary=str(draft["summary"]),
                motion=str(draft["motion"]),
                item_id=str(draft["item_id"]) if "item_id" in draft else None,
            )


@dataclass(frozen=True, slots=True)
class LongTermMemoryEntry:
    key: str
    category: str
    summary: str
    source: str
    created_at: int
    updated_at: int

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "category": self.category,
            "summary": self.summary,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_summary_dict(self) -> dict[str, str]:
        return {
            "category": self.category,
            "summary": self.summary,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class LongTermMemoryStore:
    path: Path | str

    def load(self) -> tuple[LongTermMemoryEntry, ...]:
        target = Path(self.path)
        if not target.exists():
            return ()
        try:
            payload = json.loads(target.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return ()
        rows = payload.get("entries") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return ()
        entries: list[LongTermMemoryEntry] = []
        seen: set[str] = set()
        for row in rows:
            entry = _long_term_memory_entry_from_payload(row)
            if entry is None or entry.key in seen:
                continue
            seen.add(entry.key)
            entries.append(entry)
            if len(entries) >= MAX_LONG_TERM_MEMORY_ENTRIES:
                break
        return tuple(entries)

    def save(self, entries: Iterable[LongTermMemoryEntry]) -> None:
        target = Path(self.path)
        normalized = tuple(entries)[:MAX_LONG_TERM_MEMORY_ENTRIES]
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": CURRENT_LONG_TERM_MEMORY_SCHEMA_VERSION,
            "entries": [entry.to_dict() for entry in normalized],
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class LongTermMemoryService:
    def __init__(
        self,
        entries: Iterable[LongTermMemoryEntry] = (),
        max_entries: int = MAX_LONG_TERM_MEMORY_ENTRIES,
    ) -> None:
        self.max_entries = max(1, int(max_entries))
        self.entries = tuple(
            sorted(tuple(entries), key=lambda entry: (entry.updated_at, entry.created_at, entry.key), reverse=True)
        )[: self.max_entries]

    def upsert(
        self,
        *,
        key: str,
        category: str,
        summary: str,
        source: str,
        now: int,
    ) -> LongTermMemoryEntry:
        cleaned_key = _clean_long_term_memory_text(key, MAX_LONG_TERM_MEMORY_KEY_LENGTH)
        cleaned_category = _clean_long_term_memory_text(category, MAX_LONG_TERM_MEMORY_CATEGORY_LENGTH)
        cleaned_summary = _clean_long_term_memory_text(summary, MAX_LONG_TERM_MEMORY_SUMMARY_LENGTH)
        cleaned_source = _clean_long_term_memory_text(source, MAX_LONG_TERM_MEMORY_SOURCE_LENGTH)
        if not cleaned_key or not cleaned_category or not cleaned_summary or not cleaned_source:
            raise ValueError("long-term memory requires key, category, summary, and source")
        timestamp = _clean_memory_timestamp(now)
        existing = next((entry for entry in self.entries if entry.key == cleaned_key), None)
        entry = LongTermMemoryEntry(
            key=cleaned_key,
            category=cleaned_category,
            summary=cleaned_summary,
            source=cleaned_source,
            created_at=existing.created_at if existing else timestamp,
            updated_at=timestamp,
        )
        rest = [item for item in self.entries if item.key != cleaned_key]
        self.entries = tuple([entry, *rest][: self.max_entries])
        return entry

    def summaries(self, limit: int = MAX_LONG_TERM_MEMORY_SUMMARIES) -> tuple[dict[str, str], ...]:
        capped_limit = max(0, int(limit))
        return tuple(entry.to_summary_dict() for entry in self.entries[:capped_limit])


def _long_term_memory_entry_from_payload(value: object) -> LongTermMemoryEntry | None:
    if not isinstance(value, dict):
        return None
    key = _clean_long_term_memory_text(value.get("key"), MAX_LONG_TERM_MEMORY_KEY_LENGTH)
    category = _clean_long_term_memory_text(value.get("category"), MAX_LONG_TERM_MEMORY_CATEGORY_LENGTH)
    summary = _clean_long_term_memory_text(value.get("summary"), MAX_LONG_TERM_MEMORY_SUMMARY_LENGTH)
    source = _clean_long_term_memory_text(value.get("source"), MAX_LONG_TERM_MEMORY_SOURCE_LENGTH)
    created_at = _clean_memory_timestamp(value.get("created_at"))
    updated_at = _clean_memory_timestamp(value.get("updated_at"))
    if not key or not category or not summary or not source:
        return None
    return LongTermMemoryEntry(
        key=key,
        category=category,
        summary=summary,
        source=source,
        created_at=created_at,
        updated_at=updated_at,
    )


def _clean_long_term_memory_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = "".join(" " if _is_control_character(char) else char for char in value)
    return normalized.strip()[:max_length]


def _clean_memory_timestamp(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _is_control_character(char: str) -> bool:
    return ord(char) < 32 or ord(char) == 127
