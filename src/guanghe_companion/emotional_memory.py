from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Mapping

CURRENT_EMOTIONAL_MEMORY_SCHEMA_VERSION = 1
MAX_EMOTIONAL_MEMORY_ENTRIES = 300
MAX_MEMORY_TEXT_LENGTH = 240
MAX_MEMORY_TITLE_LENGTH = 60
MAX_MEMORY_TAGS = 8
MAX_SOURCE_IDS = 8


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _clean_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    normalized = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value)
    return " ".join(normalized.strip().split())[:max_length]


def _clean_timestamp(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _clean_string_sequence(value: object, *, limit: int, item_length: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        item = _clean_text(raw, item_length)
        if not item or item in seen:
            continue
        result.append(item)
        seen.add(item)
        if len(result) >= limit:
            break
    return tuple(result)


def make_memory_id(*parts: object) -> str:
    normalized = "|".join(str(part) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True, slots=True)
class EmotionalSignal:
    label: str = "平静"
    valence: float = 0.0
    intensity: float = 0.0

    def normalized(self) -> "EmotionalSignal":
        return EmotionalSignal(
            label=_clean_text(self.label, 24) or "平静",
            valence=max(-1.0, min(1.0, float(self.valence))),
            intensity=_clamp(self.intensity),
        )

    def to_dict(self) -> dict[str, object]:
        signal = self.normalized()
        return {
            "label": signal.label,
            "valence": signal.valence,
            "intensity": signal.intensity,
        }

    @classmethod
    def from_dict(cls, value: object) -> "EmotionalSignal":
        if not isinstance(value, Mapping):
            return cls()
        try:
            valence = float(value.get("valence", 0.0))
        except (TypeError, ValueError):
            valence = 0.0
        try:
            intensity = float(value.get("intensity", 0.0))
        except (TypeError, ValueError):
            intensity = 0.0
        return cls(
            label=_clean_text(value.get("label"), 24) or "平静",
            valence=valence,
            intensity=intensity,
        ).normalized()


@dataclass(frozen=True, slots=True)
class EmotionalMemoryEntry:
    memory_id: str
    character_id: str
    owner_id: str
    kind: str
    title: str
    summary: str
    source: str
    occurred_at: int
    created_at: int
    updated_at: int
    source_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    emotion: EmotionalSignal = field(default_factory=EmotionalSignal)
    importance: float = 0.5
    relationship_delta: float = 0.0
    access_count: int = 0
    last_accessed_at: int = 0
    pinned: bool = False
    user_confirmed: bool = False
    deleted: bool = False
    supersedes: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    def normalized(self) -> "EmotionalMemoryEntry":
        return EmotionalMemoryEntry(
            memory_id=_clean_text(self.memory_id, 80),
            character_id=_clean_text(self.character_id, 80),
            owner_id=_clean_text(self.owner_id, 80) or "local_user",
            kind=_clean_text(self.kind, 40),
            title=_clean_text(self.title, MAX_MEMORY_TITLE_LENGTH),
            summary=_clean_text(self.summary, MAX_MEMORY_TEXT_LENGTH),
            source=_clean_text(self.source, 40),
            occurred_at=_clean_timestamp(self.occurred_at),
            created_at=_clean_timestamp(self.created_at),
            updated_at=_clean_timestamp(self.updated_at),
            source_ids=_clean_string_sequence(self.source_ids, limit=MAX_SOURCE_IDS, item_length=80),
            tags=_clean_string_sequence(self.tags, limit=MAX_MEMORY_TAGS, item_length=32),
            emotion=self.emotion.normalized(),
            importance=_clamp(self.importance),
            relationship_delta=max(-1.0, min(1.0, float(self.relationship_delta))),
            access_count=max(0, int(self.access_count)),
            last_accessed_at=_clean_timestamp(self.last_accessed_at),
            pinned=bool(self.pinned),
            user_confirmed=bool(self.user_confirmed),
            deleted=bool(self.deleted),
            supersedes=_clean_text(self.supersedes, 80),
            metadata=_sanitize_metadata(self.metadata),
        )

    def validate(self) -> None:
        memory = self.normalized()
        required = (
            memory.memory_id,
            memory.character_id,
            memory.owner_id,
            memory.kind,
            memory.title,
            memory.summary,
            memory.source,
        )
        if not all(required):
            raise ValueError("emotional memory requires id, character, owner, kind, title, summary, and source")

    def touch(self, now: int) -> "EmotionalMemoryEntry":
        timestamp = _clean_timestamp(now)
        return replace(
            self,
            access_count=self.access_count + 1,
            last_accessed_at=timestamp,
            updated_at=max(self.updated_at, timestamp),
        )

    def to_dict(self) -> dict[str, object]:
        memory = self.normalized()
        memory.validate()
        return {
            "memory_id": memory.memory_id,
            "character_id": memory.character_id,
            "owner_id": memory.owner_id,
            "kind": memory.kind,
            "title": memory.title,
            "summary": memory.summary,
            "source": memory.source,
            "occurred_at": memory.occurred_at,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "source_ids": list(memory.source_ids),
            "tags": list(memory.tags),
            "emotion": memory.emotion.to_dict(),
            "importance": memory.importance,
            "relationship_delta": memory.relationship_delta,
            "access_count": memory.access_count,
            "last_accessed_at": memory.last_accessed_at,
            "pinned": memory.pinned,
            "user_confirmed": memory.user_confirmed,
            "deleted": memory.deleted,
            "supersedes": memory.supersedes,
            "metadata": memory.metadata,
        }

    @classmethod
    def from_dict(cls, value: object) -> "EmotionalMemoryEntry | None":
        if not isinstance(value, Mapping):
            return None
        try:
            memory = cls(
                memory_id=_clean_text(value.get("memory_id"), 80),
                character_id=_clean_text(value.get("character_id"), 80),
                owner_id=_clean_text(value.get("owner_id"), 80) or "local_user",
                kind=_clean_text(value.get("kind"), 40),
                title=_clean_text(value.get("title"), MAX_MEMORY_TITLE_LENGTH),
                summary=_clean_text(value.get("summary"), MAX_MEMORY_TEXT_LENGTH),
                source=_clean_text(value.get("source"), 40),
                occurred_at=_clean_timestamp(value.get("occurred_at")),
                created_at=_clean_timestamp(value.get("created_at")),
                updated_at=_clean_timestamp(value.get("updated_at")),
                source_ids=_clean_string_sequence(value.get("source_ids"), limit=MAX_SOURCE_IDS, item_length=80),
                tags=_clean_string_sequence(value.get("tags"), limit=MAX_MEMORY_TAGS, item_length=32),
                emotion=EmotionalSignal.from_dict(value.get("emotion")),
                importance=float(value.get("importance", 0.5)),
                relationship_delta=float(value.get("relationship_delta", 0.0)),
                access_count=int(value.get("access_count", 0)),
                last_accessed_at=_clean_timestamp(value.get("last_accessed_at")),
                pinned=bool(value.get("pinned", False)),
                user_confirmed=bool(value.get("user_confirmed", False)),
                deleted=bool(value.get("deleted", False)),
                supersedes=_clean_text(value.get("supersedes"), 80),
                metadata=_sanitize_metadata(value.get("metadata")),
            ).normalized()
            memory.validate()
            return memory
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True, slots=True)
class CoreBondProfile:
    character_id: str
    owner_id: str = "local_user"
    player_alias: str = ""
    relationship_stage: str = "初识"
    stable_preferences: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()
    shared_rituals: tuple[str, ...] = ()
    active_story_threads: tuple[str, ...] = ()
    updated_at: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "character_id": _clean_text(self.character_id, 80),
            "owner_id": _clean_text(self.owner_id, 80) or "local_user",
            "player_alias": _clean_text(self.player_alias, 20),
            "relationship_stage": _clean_text(self.relationship_stage, 40) or "初识",
            "stable_preferences": list(_clean_string_sequence(self.stable_preferences, limit=12, item_length=80)),
            "boundaries": list(_clean_string_sequence(self.boundaries, limit=12, item_length=100)),
            "shared_rituals": list(_clean_string_sequence(self.shared_rituals, limit=8, item_length=100)),
            "active_story_threads": list(
                _clean_string_sequence(self.active_story_threads, limit=8, item_length=120)
            ),
            "updated_at": _clean_timestamp(self.updated_at),
        }

    @classmethod
    def from_dict(cls, value: object, *, fallback_character_id: str = "") -> "CoreBondProfile":
        if not isinstance(value, Mapping):
            return cls(character_id=fallback_character_id)
        return cls(
            character_id=_clean_text(value.get("character_id"), 80) or fallback_character_id,
            owner_id=_clean_text(value.get("owner_id"), 80) or "local_user",
            player_alias=_clean_text(value.get("player_alias"), 20),
            relationship_stage=_clean_text(value.get("relationship_stage"), 40) or "初识",
            stable_preferences=_clean_string_sequence(value.get("stable_preferences"), limit=12, item_length=80),
            boundaries=_clean_string_sequence(value.get("boundaries"), limit=12, item_length=100),
            shared_rituals=_clean_string_sequence(value.get("shared_rituals"), limit=8, item_length=100),
            active_story_threads=_clean_string_sequence(
                value.get("active_story_threads"), limit=8, item_length=120
            ),
            updated_at=_clean_timestamp(value.get("updated_at")),
        )


@dataclass(frozen=True, slots=True)
class MemoryChapter:
    chapter_id: str
    character_id: str
    title: str
    summary: str
    source_memory_ids: tuple[str, ...]
    created_at: int
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "chapter_id": _clean_text(self.chapter_id, 80),
            "character_id": _clean_text(self.character_id, 80),
            "title": _clean_text(self.title, 80),
            "summary": _clean_text(self.summary, 320),
            "source_memory_ids": list(
                _clean_string_sequence(self.source_memory_ids, limit=16, item_length=80)
            ),
            "created_at": _clean_timestamp(self.created_at),
            "tags": list(_clean_string_sequence(self.tags, limit=8, item_length=32)),
        }

    @classmethod
    def from_dict(cls, value: object) -> "MemoryChapter | None":
        if not isinstance(value, Mapping):
            return None
        chapter = cls(
            chapter_id=_clean_text(value.get("chapter_id"), 80),
            character_id=_clean_text(value.get("character_id"), 80),
            title=_clean_text(value.get("title"), 80),
            summary=_clean_text(value.get("summary"), 320),
            source_memory_ids=_clean_string_sequence(
                value.get("source_memory_ids"), limit=16, item_length=80
            ),
            created_at=_clean_timestamp(value.get("created_at")),
            tags=_clean_string_sequence(value.get("tags"), limit=8, item_length=32),
        )
        if not chapter.chapter_id or not chapter.character_id or not chapter.title or not chapter.summary:
            return None
        if not chapter.source_memory_ids:
            return None
        return chapter


@dataclass(frozen=True, slots=True)
class MemoryContextBundle:
    bond_profile: CoreBondProfile
    memories: tuple[EmotionalMemoryEntry, ...] = ()
    chapter: MemoryChapter | None = None

    def to_prompt_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "bond_profile": self.bond_profile.to_dict(),
        }
        if self.memories:
            payload["shared_memories"] = [
                {
                    "kind": memory.kind,
                    "title": memory.title,
                    "summary": memory.summary,
                    "emotion": memory.emotion.to_dict(),
                    "source": memory.source,
                }
                for memory in self.memories
            ]
        if self.chapter is not None:
            payload["relationship_chapter"] = self.chapter.to_dict()
        return payload

    def to_prompt_text(self) -> str:
        payload = self.to_prompt_payload()
        return json.dumps(payload, ensure_ascii=False, indent=2)


@dataclass(frozen=True, slots=True)
class EmotionalMemoryStore:
    root: Path | str
    character_id: str
    owner_id: str = "local_user"
    max_entries: int = MAX_EMOTIONAL_MEMORY_ENTRIES

    @property
    def character_root(self) -> Path:
        safe_character_id = _clean_text(self.character_id, 80) or "default"
        return Path(self.root) / "characters" / safe_character_id / "memory_v2"

    @property
    def memories_path(self) -> Path:
        return self.character_root / "emotional_memories.json"

    @property
    def profile_path(self) -> Path:
        return self.character_root / "bond_profile.json"

    @property
    def chapters_path(self) -> Path:
        return self.character_root / "memory_chapters.json"

    def load_memories(self) -> tuple[EmotionalMemoryEntry, ...]:
        payload = _read_json(self.memories_path)
        rows = payload.get("entries") if isinstance(payload, Mapping) else None
        if not isinstance(rows, list):
            return ()
        result: list[EmotionalMemoryEntry] = []
        seen: set[str] = set()
        for row in rows:
            memory = EmotionalMemoryEntry.from_dict(row)
            if memory is None or memory.character_id != self.character_id:
                continue
            if memory.memory_id in seen:
                continue
            seen.add(memory.memory_id)
            result.append(memory)
            if len(result) >= self.max_entries:
                break
        return tuple(result)

    def save_memories(self, entries: Iterable[EmotionalMemoryEntry]) -> None:
        normalized: list[EmotionalMemoryEntry] = []
        seen: set[str] = set()
        for entry in entries:
            memory = entry.normalized()
            memory.validate()
            if memory.character_id != self.character_id:
                raise ValueError("memory character_id does not match store")
            if memory.memory_id in seen:
                continue
            seen.add(memory.memory_id)
            normalized.append(memory)
            if len(normalized) >= self.max_entries:
                break
        payload = {
            "schema_version": CURRENT_EMOTIONAL_MEMORY_SCHEMA_VERSION,
            "character_id": self.character_id,
            "owner_id": self.owner_id,
            "entries": [entry.to_dict() for entry in normalized],
        }
        _write_json_atomic(self.memories_path, payload)

    def upsert_memory(self, entry: EmotionalMemoryEntry) -> EmotionalMemoryEntry:
        memory = entry.normalized()
        memory.validate()
        if memory.character_id != self.character_id:
            raise ValueError("memory character_id does not match store")
        existing = list(self.load_memories())
        rest = [item for item in existing if item.memory_id != memory.memory_id]
        self.save_memories([memory, *rest])
        return memory

    def update_memory(self, entry: EmotionalMemoryEntry) -> EmotionalMemoryEntry:
        return self.upsert_memory(entry)

    def forget_memory(self, memory_id: str, *, now: int) -> EmotionalMemoryEntry | None:
        target_id = _clean_text(memory_id, 80)
        entries = list(self.load_memories())
        updated: EmotionalMemoryEntry | None = None
        next_entries: list[EmotionalMemoryEntry] = []
        for entry in entries:
            if entry.memory_id == target_id:
                updated = replace(entry, deleted=True, updated_at=_clean_timestamp(now))
                next_entries.append(updated)
            else:
                next_entries.append(entry)
        if updated is not None:
            self.save_memories(next_entries)
        return updated

    def save_profile(self, profile: CoreBondProfile) -> None:
        if profile.character_id != self.character_id:
            raise ValueError("profile character_id does not match store")
        _write_json_atomic(
            self.profile_path,
            {
                "schema_version": CURRENT_EMOTIONAL_MEMORY_SCHEMA_VERSION,
                "profile": profile.to_dict(),
            },
        )

    def load_profile(self) -> CoreBondProfile:
        payload = _read_json(self.profile_path)
        profile = payload.get("profile") if isinstance(payload, Mapping) else None
        return CoreBondProfile.from_dict(profile, fallback_character_id=self.character_id)

    def save_chapters(self, chapters: Iterable[MemoryChapter]) -> None:
        normalized = [chapter for chapter in chapters if chapter.character_id == self.character_id]
        _write_json_atomic(
            self.chapters_path,
            {
                "schema_version": CURRENT_EMOTIONAL_MEMORY_SCHEMA_VERSION,
                "character_id": self.character_id,
                "chapters": [chapter.to_dict() for chapter in normalized[:50]],
            },
        )

    def load_chapters(self) -> tuple[MemoryChapter, ...]:
        payload = _read_json(self.chapters_path)
        rows = payload.get("chapters") if isinstance(payload, Mapping) else None
        if not isinstance(rows, list):
            return ()
        chapters = [MemoryChapter.from_dict(row) for row in rows]
        return tuple(
            chapter
            for chapter in chapters
            if chapter is not None and chapter.character_id == self.character_id
        )

    def upsert_chapter(self, chapter: MemoryChapter) -> MemoryChapter:
        if chapter.character_id != self.character_id:
            raise ValueError("chapter character_id does not match store")
        rest = [item for item in self.load_chapters() if item.chapter_id != chapter.chapter_id]
        self.save_chapters([chapter, *rest])
        return chapter


def _sanitize_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, object] = {}
    for raw_key, raw_value in value.items():
        key = _clean_text(raw_key, 40)
        if not key:
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            result[key] = raw_value
        elif isinstance(raw_value, (list, tuple)):
            result[key] = [
                item
                for item in raw_value[:16]
                if isinstance(item, (str, int, float, bool)) or item is None
            ]
    return result


def _read_json(path: Path) -> object:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
